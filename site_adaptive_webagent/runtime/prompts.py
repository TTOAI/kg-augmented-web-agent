"""Site-configurable prompt library.

 scaffold 여러 파일에 흩어져 있던 prompt fragment를 통합한 layer.
각 site는 `config/sites/<site>/prompts.yaml`에 해당 site의 field/role 어휘가 담긴
prompt 구조를 제공하고, runtime은 이 library를 조회해 prompt 단편을 합성한다.

API:
    lib = load_prompt_library("gitlab")
    mutate_checklist_text = lib.render_mutate_checklist()
    filter_preamble_text = lib.render_filter_template_preamble()
    goto_desc, goto_url_desc = lib.goto_tool_description()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SITE = "gitlab"


def _site_dir(site: str = DEFAULT_SITE) -> Path:
    return Path("config/sites") / site


@dataclass(frozen=True)
class PromptLibrary:
    """In-memory prompt library loaded from prompts.yaml."""

    # raw parsed YAML (각 render helper가 필요한 키를 직접 읽는다).
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "PromptLibrary":
        return cls(raw={})

    # ---- rendering helpers ----

    def render_mutate_checklist(self) -> str:
        """`## Form submission checklist (MUTATE)` 섹션을 한 문자열로 합성.

        missing data 시 empty string 반환 (caller는 checklist injection skip).
        """
        mc = self.raw.get("mutate_checklist")
        if not isinstance(mc, dict):
            return ""
        lines: list[str] = []
        header = mc.get("header") or ""
        if header:
            lines.append(f"## {header}")
        preamble = mc.get("preamble") or ""
        if preamble:
            lines.append(preamble)
        for entry in mc.get("qualifiers") or []:
            kws = entry.get("keywords") or []
            action = entry.get("action") or ""
            if not (kws and action):
                continue
            lines.append(f"  - {' / '.join(str(k) for k in kws)} → {action}")

        vr = mc.get("verb_routing")
        if isinstance(vr, dict):
            lines.append("")
            vh = vr.get("header") or ""
            if vh:
                lines.append(f"### {vh}")
            vp = vr.get("preamble") or ""
            if vp:
                lines.append(vp)
            for verb_entry in vr.get("verbs") or []:
                verb_set = verb_entry.get("verb_set") or []
                guidance = verb_entry.get("guidance") or ""
                if not (verb_set and guidance):
                    continue
                verbs = " / ".join(str(v) for v in verb_set)
                lines.append(f"  - {verbs} → {guidance.strip()}")

        closing = mc.get("closing") or ""
        if closing:
            lines.append("")
            lines.append(closing.strip())
        return "\n".join(lines)

    def render_filter_template_preamble(self) -> list[str]:
        """Filter template section의 preamble 줄 목록 반환.

        hint_generator의 `_render_filter_templates`가 templates 렌더 앞에 삽입.
        """
        ft = self.raw.get("filter_template_preamble")
        if not isinstance(ft, dict):
            return []
        lines: list[str] = []
        header = ft.get("header") or ""
        if header:
            lines.append(f"## {header}")
        body = ft.get("body") or ""
        if body:
            lines.append(body.strip())
        emphasis = ft.get("emphasis") or ""
        if emphasis:
            lines.append(emphasis.strip())
        lines.append("")
        return lines

    def goto_tool_description(self) -> tuple[str, str]:
        """Return (description, url_param_description). Fallback to empty strings."""
        gt = self.raw.get("goto_tool")
        if not isinstance(gt, dict):
            return ("", "")
        desc = (gt.get("description") or "").strip()
        url_desc = (gt.get("url_description") or "").strip()
        return (desc, url_desc)


def load_prompt_library(site: str = DEFAULT_SITE) -> PromptLibrary:
    """Load `<site_dir>/prompts.yaml`. Returns empty library if file missing."""
    path = _site_dir(site) / "prompts.yaml"
    if not path.exists():
        return PromptLibrary.empty()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return PromptLibrary.empty()
    if not isinstance(raw, dict):
        return PromptLibrary.empty()
    return PromptLibrary(raw=raw)


# Module-level default library (lazy-loaded, cached). 대부분 caller는 별도 DI 없이
# default site의 library 사용. Test에서는 `load_prompt_library("other_site")` 호출.
_DEFAULT_LIBRARY: PromptLibrary | None = None


def default_prompt_library() -> PromptLibrary:
    """Return module-level cached default library (lazy)."""
    global _DEFAULT_LIBRARY
    if _DEFAULT_LIBRARY is None:
        import os
        site = os.getenv("SITE_NAME", DEFAULT_SITE)
        _DEFAULT_LIBRARY = load_prompt_library(site)
    return _DEFAULT_LIBRARY
