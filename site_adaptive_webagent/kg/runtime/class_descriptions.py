"""Load and format per-class descriptions for target_class inference prompt.

Descriptions are pre-built by `scripts/kg_solution/build_class_descriptions.py`
into `output/validation/kg_solution/class_descriptions.json` and loaded once
per `run_agent()` invocation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_PATH = Path("output/validation/kg_solution/class_descriptions.json")


@dataclass(frozen=True)
class FilterTemplate:
    label: str
    path_template: str
    query_example: str
    query_signature: str


@dataclass(frozen=True)
class FilterOption:
    name: str
    value: str = ""


@dataclass(frozen=True)
class FilterControl:
    """An in-page dropdown/menu with enumerated options.

    Example: {label: "Label", param: "label_name[]",
              options: [{name: "bug"}, {name: "feature"}, ...]}
    """
    label: str
    param: str
    options: tuple[FilterOption, ...]
    instance_freq: int = 1


@dataclass(frozen=True)
class FilterCategory:
    """A filter category captured via recursive expansion of a filtered-search
    input (3-level: category → operator → value).

    name: category label (e.g. "Label", "Assignee", "Milestone")
    param: URL query param for `goto(?param=value)` (e.g. "label_name[]")
    operators: list of operator labels (e.g. ["=\\nis", "!=\\nis not"])
    example_values: sample values observed during existence-proof click; NOT a
        complete inventory. Agent is expected to supply the actual value from
        task context.
    has_values: whether at least one value appeared in the L3 menu (existence).
    """
    name: str
    param: str = ""
    operators: tuple[str, ...] = ()
    example_values: tuple[str, ...] = ()
    has_values: bool = False


@dataclass(frozen=True)
class ModalInput:
    role: str
    name: str = ""
    label: str = ""
    placeholder: str = ""
    has_popup: str = ""
    autocomplete: str = ""
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModalStructure:
    """Dialog-opening interaction captured by clicking an aria-haspopup=dialog
    trigger and scraping the modal's form-like contents.

    trigger_label: button text that opens the modal
    inputs: input/select/textbox/combobox/searchbox elements inside the modal
    submit_labels: submit-type button labels
    form_action: action URL of the modal's form (if any)
    form_method: HTTP method of the form (POST/PATCH/etc.)
    """
    trigger_label: str
    inputs: tuple[ModalInput, ...] = ()
    submit_labels: tuple[str, ...] = ()
    form_action: str = ""
    form_method: str = ""


@dataclass(frozen=True)
class ClassDescription:
    class_name: str
    url_template: Optional[str]
    description: str
    filter_templates: tuple[FilterTemplate, ...] = ()
    filter_controls: tuple[FilterControl, ...] = ()
    filter_categories: tuple[FilterCategory, ...] = ()
    modal_structures: tuple[ModalStructure, ...] = ()
    # Structured fields for target inference disambiguation.
    scope: str = ""                         # "user" | "project" | "group" | "admin" | "site" | ...
    role: str = ""                          # one-line natural description
    triggers: tuple[str, ...] = ()          # intent phrases that map to this class
    not_for: tuple[str, ...] = ()           # disambiguator phrases (this class should NOT be picked)
    typical_query_params: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClassCatalog:
    entries: dict[str, ClassDescription]

    @property
    def class_names(self) -> list[str]:
        return list(self.entries.keys())

    def __contains__(self, cls: str) -> bool:
        return cls in self.entries

    def get(self, cls: str) -> Optional[ClassDescription]:
        return self.entries.get(cls)

    def format_for_prompt(self, include_url: bool = True) -> str:
        """Render each class as a multi-line structured block.

        Structured fields (scope/role/triggers/not_for) help the LLM
        disambiguate between sibling classes whose URL or name alone is
        ambiguous (e.g., dashboard/issue_list vs project/issue_list).
        Falls back to single-line format for classes without structured data.
        """
        blocks: list[str] = []
        for cls in sorted(self.entries):
            e = self.entries[cls]
            has_structured = bool(e.scope or e.role or e.triggers or e.not_for)
            if not has_structured:
                # Legacy single-line rendering.
                parts = [f"- {cls}"]
                if include_url and e.url_template:
                    parts.append(f"URL={e.url_template}")
                if e.description:
                    parts.append(e.description)
                blocks.append(" | ".join(parts))
                continue
            lines = [f"- {cls}"]
            if include_url and e.url_template:
                lines.append(f"    url: {e.url_template}")
            if e.scope:
                lines.append(f"    scope: {e.scope}")
            if e.role:
                lines.append(f"    role: {e.role}")
            if e.triggers:
                lines.append(f"    triggers: {', '.join(e.triggers)}")
            if e.not_for:
                lines.append(f"    not_for: {', '.join(e.not_for)}")
            if e.typical_query_params:
                lines.append(
                    f"    typical_query_params: {', '.join(e.typical_query_params)}"
                )
            blocks.append("\n".join(lines))
        return "\n".join(blocks)


def load_class_catalog(path: Optional[Path] = None) -> ClassCatalog:
    path = path or DEFAULT_PATH
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries: dict[str, ClassDescription] = {}
    for cls, payload in data["entries"].items():
        ft_raw = payload.get("filter_templates") or []
        filter_templates = tuple(
            FilterTemplate(
                label=str(ft.get("label") or ""),
                path_template=str(ft.get("path_template") or ""),
                query_example=str(ft.get("query_example") or ""),
                query_signature=str(ft.get("query_signature") or ""),
            )
            for ft in ft_raw
        )
        fc_raw = payload.get("filter_controls") or []
        filter_controls = tuple(
            FilterControl(
                label=str(fc.get("label") or ""),
                param=str(fc.get("param") or ""),
                options=tuple(
                    FilterOption(
                        name=str(opt.get("name") or ""),
                        value=str(opt.get("value") or ""),
                    )
                    for opt in (fc.get("options") or [])
                ),
                instance_freq=int(fc.get("instance_freq") or 1),
            )
            for fc in fc_raw
            if isinstance(fc, dict) and fc.get("label")
        )
        fcat_raw = payload.get("filter_categories") or []
        filter_categories = tuple(
            FilterCategory(
                name=str(fc.get("name") or ""),
                param=str(fc.get("param") or ""),
                operators=tuple(str(op) for op in (fc.get("operators") or [])),
                example_values=tuple(
                    str(v) for v in (fc.get("example_values") or [])
                ),
                has_values=bool(fc.get("has_values")),
            )
            for fc in fcat_raw
            if isinstance(fc, dict) and fc.get("name")
        )
        modal_raw = payload.get("modal_structures") or []
        modal_structures = tuple(
            ModalStructure(
                trigger_label=str(m.get("trigger_label") or ""),
                inputs=tuple(
                    ModalInput(
                        role=str(inp.get("role") or ""),
                        name=str(inp.get("name") or ""),
                        label=str(inp.get("label") or ""),
                        placeholder=str(inp.get("placeholder") or ""),
                        has_popup=str(inp.get("has_popup") or ""),
                        autocomplete=str(inp.get("autocomplete") or ""),
                        options=tuple(
                            str(o) for o in (inp.get("options") or [])
                        ),
                    )
                    for inp in (m.get("inputs") or [])
                ),
                submit_labels=tuple(
                    str(s) for s in (m.get("submit_labels") or [])
                ),
                form_action=str(m.get("form_action") or ""),
                form_method=str(m.get("form_method") or ""),
            )
            for m in modal_raw
            if isinstance(m, dict) and m.get("trigger_label")
        )
        entries[cls] = ClassDescription(
            class_name=cls,
            url_template=payload.get("url_template"),
            description=payload.get("description") or "",
            filter_templates=filter_templates,
            filter_controls=filter_controls,
            filter_categories=filter_categories,
            modal_structures=modal_structures,
            scope=str(payload.get("scope") or ""),
            role=str(payload.get("role") or ""),
            triggers=tuple(str(t) for t in (payload.get("triggers") or [])),
            not_for=tuple(str(t) for t in (payload.get("not_for") or [])),
            typical_query_params=tuple(
                str(p) for p in (payload.get("typical_query_params") or [])
            ),
        )
    return ClassCatalog(entries=entries)
