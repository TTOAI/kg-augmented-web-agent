"""KGSession — runtime wrapper tying classifier + KG + LLM for the agent.

Built once at `run_agent()` entry via `build_kg_session()`. Returns None on
any load/auth failure; callers treat None as "no-hint mode" and run baseline
behavior. All per-call errors inside KGSession methods are caught and
logged, returning graceful defaults so KG issues never break task execution.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from scripts.kg.utils.classify import load_classifier

from site_adaptive_webagent.runtime.llm import (
    AnthropicLLMClient,
    LLMClient,
    OpenAILLMClient,
)

from site_adaptive_webagent.kg.site_extras import load_site_cascade

from .class_descriptions import ClassCatalog, FilterTemplate, load_class_catalog
from .hint_generator import generate_hint as _generate_hint
from .path_finder import (
    CascadeConfig,
    PathResult,
    find_path as _find_path,
)
from .task_inferrer import InferResult, infer_target as _infer_target

logger = logging.getLogger("webarena_verified")

DEFAULT_RULES_PATH = Path("output/validation/rules/class_rules.json")
DEFAULT_EDGE_GRAPH_PATH = Path("output/validation/stage_c/edge_graph.json")
DEFAULT_CLASS_DESC_PATH = Path(
    "output/validation/kg_solution/class_descriptions.json"
)
DEFAULT_ACTION_CATALOG_PATH = Path(
    "output/validation/stage_b/action_catalog.json"
)


@dataclass
class SubGoalKGContext:
    """Per-sub-goal KG state: inferred target + cached path for no-replan variant."""

    target_class: Optional[str]
    bindings: dict[str, str] = field(default_factory=dict)
    agreement: int = 0
    rejected_out_of_set: list[str] = field(default_factory=list)
    # Populated lazily on first find_path call; reused if replan disabled.
    cached_initial_path: Optional[PathResult] = None


@dataclass
class KGSession:
    classifier: Callable[[str], Optional[str]]
    adjacency: dict
    all_classes: set[str]
    catalog: ClassCatalog
    inferrer_llm: LLMClient
    hint_llm: Optional[LLMClient]
    cascade_config: CascadeConfig
    cascade_enabled: bool = True
    replan_per_step: bool = True
    hint_cache: dict = field(default_factory=dict)
    k_samples: int = 3
    action_catalog: dict = field(default_factory=dict)
    expose_actions: bool = True

    def classify_url(self, url: str) -> Optional[str]:
        try:
            return self.classifier(url)
        except Exception as exc:
            logger.warning("[KG] classifier failed for url=%s: %s", url, exc)
            return None

    def infer_target_for_sub_goal(
        self, sub_goal: str, task: str
    ) -> SubGoalKGContext:
        # V1-tc ablation gate: target classifier 비활성. page-surface 힌트만 노출되도록
        # target_class=None을 반환. caller(executor)는 target=None을 stay_and_explore
        # path로 처리해 현재 클래스의 액션·필터 카탈로그만 hint에 담는다.
        if os.getenv("KG_DISABLE_TARGET_INFERRER", "").strip().lower() in (
            "1", "true", "yes", "on"
        ):
            logger.info("[KG] target inferrer disabled (V1-tc ablation)")
            return SubGoalKGContext(target_class=None)
        try:
            result: InferResult = _infer_target(
                sub_goal=sub_goal,
                task=task,
                catalog=self.catalog,
                llm=self.inferrer_llm,
                k=self.k_samples,
            )
        except Exception as exc:
            logger.warning("[KG] infer_target failed: %s", exc)
            return SubGoalKGContext(target_class=None)
        logger.info(
            "[KG] inferred target=%s agreement=%d/%d rejected=%s",
            result.target_class,
            result.agreement,
            self.k_samples,
            result.rejected_out_of_set,
        )
        return SubGoalKGContext(
            target_class=result.target_class,
            bindings=result.bindings,
            agreement=result.agreement,
            rejected_out_of_set=result.rejected_out_of_set,
        )

    def find_path(self, current: str, target: str) -> PathResult:
        try:
            result = _find_path(
                self.adjacency,
                current,
                target,
                all_classes=self.all_classes,
                config=self.cascade_config,
            )
        except Exception as exc:
            logger.warning("[KG] find_path failed: %s", exc)
            return PathResult(
                strategy="failed",
                actual_target=target,
                inferred_target=target,
                note=f"find_path exception: {exc}",
            )
        if not self.cascade_enabled and result.strategy in (
            "family_sibling",
            "scope_entry",
            "hub_fallback",
        ):
            return PathResult(
                strategy="stay_and_explore",
                actual_target=current,
                inferred_target=target,
                note=(
                    f"Cascade disabled (V1b). Exact path to {target!r} "
                    f"unavailable; staying for local exploration."
                ),
                progress_checked=True,
            )
        return result

    def get_class_actions(self, class_name: str) -> Optional[dict]:
        """Return the action catalog entry for class_name, or None if absent.

        Catalog entry shape (from stage_b/action_catalog.json):
            {"instance_count": int, "raw_action_count": int,
             "navigation_actions": [{"label", "target_class", "sample_href",
                                     "tag", "role", "instance_freq",
                                     "self_edge"}, ...],
             "internal_actions": [{"label", "tag", "role", "type",
                                   "instance_freq"}, ...]}
        """
        if not class_name:
            return None
        entry = self.action_catalog.get(class_name)
        if entry is None:
            return None
        return entry

    def get_filter_templates(self, class_name: str) -> list:
        """Return FilterTemplate list for class_name.

        class 자신에 관측된 filter template이 없어도, 같은 **family / list-type
        siblings**에서 템플릿을 수집해 cross-class generalization hint를 제공한다.
        예: project/issue_list에 직접 관측된 filter가 없어도 project/merge_request_list,
        dashboard/issue_list의 state=opened, label_name[]=, assignee_username= 같은
        패턴을 볼 수 있어 agent가 pattern을 추론 가능.

         F2: cross-class로 가져온 template의 `path_template`을 **current class의
        url_template**으로 rewrite한다. 원본 sibling의 path (예: `/-/merge_requests`)을
        그대로 보여주면 agent가 현재 endpoint (`/-/issues`)에 외삽하기 어렵다. Rewrite
        후에는 `state=opened` 같은 query가 `/-/issues?state=opened` 형태로 agent에게
        직접 제시되어 goto 경로가 분명해진다.
        """
        if not class_name:
            return []
        seen_sigs: set[str] = set()
        out: list = []

        current_entry = self.catalog.get(class_name)
        current_path_tpl = current_entry.url_template if current_entry else None

        def _append(entry, rewrite_path: bool = False) -> None:
            if entry is None:
                return
            for ft in entry.filter_templates:
                sig = getattr(ft, "query_signature", "")
                if not sig or sig in seen_sigs:
                    continue
                seen_sigs.add(sig)
                if rewrite_path and current_path_tpl:
                    ft = FilterTemplate(
                        label=ft.label,
                        path_template=current_path_tpl,
                        query_example=ft.query_example,
                        query_signature=ft.query_signature,
                    )
                out.append(ft)

        # 1. class 자신 — path 그대로 (이미 current endpoint)
        _append(current_entry, rewrite_path=False)

        # 2. same-scope siblings with "list" suffix (filter 경향이 유사)
        parts = class_name.split("/")
        if len(parts) >= 2:
            scope = parts[0]
            is_list_type = class_name.endswith("_list") or "/list" in class_name
            for other_name, other_entry in self.catalog.entries.items():
                if other_name == class_name:
                    continue
                if not other_name.startswith(f"{scope}/"):
                    continue
                # list-type끼리만, 또는 target이 list면 sibling list도 포함
                if is_list_type and (
                    other_name.endswith("_list") or "/list" in other_name
                ):
                    _append(other_entry, rewrite_path=True)

        # 3. cross-scope siblings with same base name (예: project/issue_list
        #    → dashboard/issue_list)
        if len(parts) >= 2:
            # 사이트별 variant_segments는 cascade_config에서 로드 (Tier 3b 사이트 무관
            # refactor). 비어 있으면 path_finder 모듈 상수로 fallback.
            from site_adaptive_webagent.kg.runtime.path_finder import (
                VARIANT_SEGMENTS as _DEFAULT_VARIANT_SEGMENTS,
            )
            variant_segments = (
                self.cascade_config.variant_segments
                if self.cascade_config and self.cascade_config.variant_segments
                else _DEFAULT_VARIANT_SEGMENTS
            )
            base_name = parts[-1] if parts[-1] not in variant_segments else (
                parts[-2] if len(parts) >= 2 else parts[-1]
            )
            for other_name, other_entry in self.catalog.entries.items():
                if other_name == class_name:
                    continue
                other_parts = other_name.split("/")
                if len(other_parts) >= 2 and base_name in other_parts[-2:]:
                    _append(other_entry, rewrite_path=True)

        return out[:12]  # total cap

    def generate_hint(
        self,
        path_result: PathResult,
        *,
        current: str,
        task: str,
        bindings: dict[str, str],
        current_class_actions: Optional[dict] = None,
        filter_templates: Optional[list] = None,
    ) -> Optional[str]:
        try:
            return _generate_hint(
                path_result,
                current=current,
                task=task,
                bindings=bindings,
                llm=self.hint_llm,
                cache=self.hint_cache,
                current_class_actions=current_class_actions,
                filter_templates=filter_templates,
            )
        except Exception as exc:
            logger.warning("[KG] generate_hint failed: %s", exc)
            return None


def _make_inferrer_llm(temperature: float) -> Optional[LLMClient]:
    """Dedicated LLM client for target inference; requires non-zero temperature
    so that K-sample self-consistency can observe variance."""
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            return None
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        return OpenAILLMClient(model=model, temperature=temperature)
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    return AnthropicLLMClient(model=model, temperature=temperature)


def build_kg_session(
    rules_path: Path = DEFAULT_RULES_PATH,
    edge_graph_path: Path = DEFAULT_EDGE_GRAPH_PATH,
    class_desc_path: Path = DEFAULT_CLASS_DESC_PATH,
    action_catalog_path: Path = DEFAULT_ACTION_CATALOG_PATH,
    *,
    site_name: str = "gitlab",
    inferrer_temperature: float = 0.3,
    cascade_enabled: bool = True,
    replan_per_step: bool = True,
    expose_actions: bool = True,
    k_samples: int = 3,
) -> Optional[KGSession]:
    """Build a KG session, or return None on any failure (graceful fallback)."""
    try:
        classifier = load_classifier(rules_path)
    except Exception as exc:
        logger.warning("[KG] classifier load failed: %s", exc)
        return None
    try:
        edge_data = json.loads(Path(edge_graph_path).read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("[KG] edge_graph load failed: %s", exc)
        return None
    try:
        catalog = load_class_catalog(class_desc_path)
    except Exception as exc:
        logger.warning("[KG] class_descriptions load failed: %s", exc)
        return None
    # Action catalog is advisory data; failure only disables action exposure.
    action_catalog: dict = {}
    try:
        ac_data = json.loads(Path(action_catalog_path).read_text(encoding="utf-8"))
        action_catalog = ac_data.get("catalog", {}) if isinstance(ac_data, dict) else {}
    except Exception as exc:
        logger.warning(
            "[KG] action_catalog load failed: %s — proceeding without it", exc
        )
    inferrer_llm = _make_inferrer_llm(inferrer_temperature)
    if inferrer_llm is None:
        logger.warning(
            "[KG] LLM client unavailable (missing API key); KG disabled."
        )
        return None
    #  -3b: cascade config를 site_name 기반으로 외부 YAML에서 로드.
    # 이전엔 path_finder의 DEFAULT_GITLAB_CONFIG를 직접 주입했음. 에서
    # variant_segments / family_type_suffixes도 함께 로드.
    site_cascade = load_site_cascade(site_name)
    cascade_cfg = CascadeConfig(
        scope_entries=dict(site_cascade.scope_entries),
        hub=site_cascade.hub,
        variant_segments=site_cascade.variant_segments,
        family_type_suffixes=site_cascade.family_type_suffixes,
    )
    if not cascade_cfg.scope_entries:
        logger.warning(
            "[KG] cascade config empty for site=%s — cascade stages will "
            "degrade to stay_and_explore; check config/sites/%s/cascade.yaml",
            site_name, site_name,
        )
    all_classes = set(edge_data["adjacency"].keys())
    for e in edge_data.get("edges", []):
        all_classes.add(e["target"])
    logger.info(
        "[KG] session loaded: classes=%d edges=%d catalog_classes=%d cascade=%s replan=%s expose_actions=%s site=%s",
        len(all_classes),
        len(edge_data.get("edges", [])),
        len(action_catalog),
        cascade_enabled,
        replan_per_step,
        expose_actions,
        site_name,
    )
    return KGSession(
        classifier=classifier,
        adjacency=edge_data["adjacency"],
        all_classes=all_classes,
        catalog=catalog,
        inferrer_llm=inferrer_llm,
        hint_llm=inferrer_llm,
        cascade_config=cascade_cfg,
        cascade_enabled=cascade_enabled,
        replan_per_step=replan_per_step,
        k_samples=k_samples,
        action_catalog=action_catalog,
        expose_actions=expose_actions,
    )
