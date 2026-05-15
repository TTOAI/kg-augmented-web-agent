"""CrawlResult → SiteKG 변환 (crawler의 offline 후처리).

`playwright_crawler.crawl_site`가 만든 list[CrawlResult]를 받아
`source="crawl"` / `trust="verified"` 노드·엣지로 구성된 SiteKG를 생산한다.

산출된 SiteKG는 `SiteKGStore.merge`로 manual seed에 병합된다.
id 충돌을 피하기 위해 모든 crawl 노드는 `crawl:` prefix를 사용.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Iterable
from urllib.parse import urlparse

from ..types import (
    Action,
    IdentityParam,
    LeadsToEdge,
    SiteConfig,
    SiteKG,
    StatePattern,
    default_trust_for_source,
)
from ..urlnorm import normalize_url
from .playwright_crawler import CrawlResult, FormElementMeta

CRAWL_TRUST = default_trust_for_source("crawl")  # "verified"
_CRAWL_PREFIX = "crawl:"


def extract_url_template(
    urls: list[str],
    site_config: SiteConfig,
) -> tuple[str, dict[str, dict[str, object]]]:
    """다중 관찰 URL → 공통 url_template + path_params 추출.

    각 URL의 path를 segment 단위로 비교, 같은 위치에 다른 token이 나타나면
    `{slot_N}` placeholder로 일반화. 한 URL만 주어지면 path 그대로 반환 (slot 없음).

    예:
      ["/foo/bar/-/issues", "/baz/qux/-/issues"]
      → ("/{slot_0}/{slot_1}/-/issues",
         {"slot_0": {"type": "segment"}, "slot_1": {"type": "segment"}})

    슬롯 이름은 generic (`slot_N`). 의미 있는 이름(예: `project_path`)은
    LLM derivation 또는 manual verification 단계에서 부여.
    """
    if not urls:
        return ("", {})

    # path만 추출하고 정규화 (query 제거)
    paths: list[list[str]] = []
    for url in urls:
        parsed = urlparse(url)
        path = parsed.path or "/"
        # site_config alias 적용
        nu = normalize_url(path, site_config, runtime_context=None)
        paths.append(_split_segments(nu.path))

    if len(paths) == 1:
        return ("/" + "/".join(paths[0]), {})

    # 모든 path의 길이가 같아야 같은 template으로 판정
    seg_count = len(paths[0])
    if not all(len(p) == seg_count for p in paths):
        # 길이가 다르면 generalize 어려움 — 가장 짧은 path 그대로 반환 (slot 없음)
        shortest = min(paths, key=len)
        return ("/" + "/".join(shortest), {})

    # segment 단위 비교: 모두 같으면 literal, 다르면 slot
    template_segs: list[str] = []
    path_params: dict[str, dict[str, object]] = {}
    slot_idx = 0
    for col in range(seg_count):
        col_values = {p[col] for p in paths}
        if len(col_values) == 1:
            template_segs.append(next(iter(col_values)))
        else:
            slot_name = f"slot_{slot_idx}"
            template_segs.append("{" + slot_name + "}")
            path_params[slot_name] = {"type": "segment"}
            slot_idx += 1

    return ("/" + "/".join(template_segs), path_params)


def crawl_results_to_sitekg(
    crawl_results: Iterable[CrawlResult],
    site_config: SiteConfig,
    site: str = "",
) -> SiteKG:
    """CrawlResult 컬렉션을 source=crawl SiteKG로 변환.

    그룹화 규칙:
    - 같은 normalized_url_template으로 모이는 URL → 단일 StatePattern
    - 관찰된 query param 이름 → IdentityParam (type=string 기본)
    - parent_url → child_url 전이 → LeadsToEdge 후보 (action_name=`crawl:nav`)
    - form_elements → Action 후보 (action_name=`crawl:form:<path>`)

    이 단계는 미세 분류(InfoType, enum 값, default)를 수행하지 않는다 —
    LLM derivation과 수동 검증 단계의 책임.
    """
    crawl_results = list(crawl_results)
    kg = SiteKG(site=site)

    if not crawl_results:
        return kg

    # 1. normalized_url_template 기준으로 그룹화
    by_template: dict[str, list[CrawlResult]] = defaultdict(list)
    for cr in crawl_results:
        if cr.http_status >= 400:
            continue  # 실패 페이지는 skip
        by_template[cr.normalized_url_template].append(cr)

    # 2. 각 그룹 → StatePattern
    pattern_id_by_template: dict[str, str] = {}
    for template, group in by_template.items():
        pattern_id = _make_pattern_id(template)
        pattern_id_by_template[template] = pattern_id

        # path_params: 각 CrawlResult의 path_params를 union
        merged_path_params: dict[str, dict[str, object]] = {}
        for cr in group:
            for slot, meta in cr.path_params.items():
                merged_path_params.setdefault(slot, dict(meta))

        # query params: 관찰된 이름 union → IdentityParam
        param_names: list[str] = []
        for cr in group:
            for q in cr.query_params_seen:
                if q not in param_names:
                    param_names.append(q)
        identity_params = [IdentityParam(name=n, type="string") for n in param_names]

        kg.state_patterns[pattern_id] = StatePattern(
            id=pattern_id,
            url_template=template,
            path_params=merged_path_params,
            identity_query_params=identity_params,
            canonical_emit_order=list(param_names),
            url_template_trust=CRAWL_TRUST,
            source="crawl",
        )

    # 3. parent_url → child_url 전이를 LeadsToEdge로 누적 (중복 제거)
    seen_edges: set[tuple[str, str, str]] = set()
    nav_action_name = f"{_CRAWL_PREFIX}nav"
    nav_action_added = False
    for cr in crawl_results:
        if cr.http_status >= 400 or cr.parent_url is None:
            continue
        # parent의 template과 자기 template을 찾기 위해 reverse lookup
        parent_template = _find_template_for_url(cr.parent_url, by_template)
        if parent_template is None:
            continue
        from_id = pattern_id_by_template.get(parent_template)
        to_id = pattern_id_by_template.get(cr.normalized_url_template)
        if from_id is None or to_id is None or from_id == to_id:
            continue
        key = (from_id, nav_action_name, to_id)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        if not nav_action_added:
            kg.actions[nav_action_name] = Action(
                name=nav_action_name,
                params=[{"name": "url", "type": "string"}],
                description="Generic navigation transition observed by crawler.",
                source="crawl",
            )
            nav_action_added = True
        kg.leads_to_edges.append(
            LeadsToEdge(
                from_state_pattern_id=from_id,
                action_name=nav_action_name,
                to_state_pattern_id=to_id,
                trust=CRAWL_TRUST,
                source="crawl",
            )
        )

    # 4. form_elements → Action 후보 + LeadsToEdge (target은 form.action_url 기반)
    # form.action_url이 관찰된 다른 page와 일치하면 cross-page edge, 그렇지 않으면
    # self-loop fallback. 이렇게 해야 글로벌 search bar 같은 cross-target form이
    # 정확한 target state를 가리키고, post-enrich가 query param을 옳은 state에 박는다.
    literal_path_to_template: dict[str, str] = {}
    for cr in crawl_results:
        if cr.http_status >= 400:
            continue
        literal_path = urlparse(cr.url).path or "/"
        literal_path_to_template.setdefault(literal_path, cr.normalized_url_template)

    seen_form_actions: set[str] = set()
    seen_form_edges: set[tuple[str, str, str]] = set()
    for cr in crawl_results:
        if cr.http_status >= 400:
            continue
        state_id = pattern_id_by_template.get(cr.normalized_url_template)
        if state_id is None:
            continue
        for form in cr.form_elements:
            action_name = _make_form_action_name(form)
            if action_name not in seen_form_actions:
                seen_form_actions.add(action_name)
                kg.actions[action_name] = Action(
                    name=action_name,
                    params=[{"name": form.name, "type": form.type}],
                    description=(
                        f"Crawler-observed form input {form.name!r} on page "
                        f"{cr.normalized_url_template!r} (type={form.type}, "
                        f"method={form.method}, action_url={form.action_url!r})."
                    ),
                    source="crawl",
                )
            # Edge target 결정: form.action_url path → known template → state_id.
            # Lookup 실패 시 self-loop (in-place form filter 가정).
            target_id = state_id
            if form.action_url:
                target_path = urlparse(form.action_url).path or ""
                target_template = literal_path_to_template.get(target_path)
                if target_template is not None:
                    resolved = pattern_id_by_template.get(target_template)
                    if resolved is not None:
                        target_id = resolved
            edge_key = (state_id, action_name, target_id)
            if edge_key in seen_form_edges:
                continue
            seen_form_edges.add(edge_key)
            kg.leads_to_edges.append(
                LeadsToEdge(
                    from_state_pattern_id=state_id,
                    action_name=action_name,
                    to_state_pattern_id=target_id,
                    trust=CRAWL_TRUST,
                    source="crawl",
                )
            )

    return kg


def _split_segments(path: str) -> list[str]:
    """path를 segment list로 (leading/trailing slash 제거 후)."""
    stripped = path.strip("/")
    if not stripped:
        return []
    return stripped.split("/")


def _make_pattern_id(template: str) -> str:
    """url_template에서 안정적이고 고유한 StatePattern id 생성.

    Manual seed와의 충돌을 피하기 위해 `crawl:` prefix + template hash 사용.
    """
    digest = hashlib.sha1(template.encode("utf-8")).hexdigest()[:10]
    # 사람이 읽기 쉬운 sluggified suffix (선택)
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", template).strip("_")[:40] or "root"
    return f"{_CRAWL_PREFIX}{slug}__{digest}"


def _make_form_action_name(form: FormElementMeta) -> str:
    """form input → Action name."""
    if form.action_url:
        path = urlparse(form.action_url).path or "/"
    else:
        path = "/"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", path).strip("_") or "root"
    return f"{_CRAWL_PREFIX}form:{slug}:{form.name}"


def _find_template_for_url(
    url: str,
    by_template: dict[str, list[CrawlResult]],
) -> str | None:
    """주어진 url이 속한 template을 찾는다 (역방향 lookup)."""
    for template, group in by_template.items():
        for cr in group:
            if cr.url == url:
                return template
    return None
