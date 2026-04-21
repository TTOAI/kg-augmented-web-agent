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
class ClassDescription:
    class_name: str
    url_template: Optional[str]
    description: str


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
        """One line per class, ordered deterministically."""
        lines = []
        for cls in sorted(self.entries):
            e = self.entries[cls]
            parts = [f"- {cls}"]
            if include_url and e.url_template:
                parts.append(f"URL={e.url_template}")
            if e.description:
                parts.append(e.description)
            lines.append(" | ".join(parts))
        return "\n".join(lines)


def load_class_catalog(path: Optional[Path] = None) -> ClassCatalog:
    path = path or DEFAULT_PATH
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries: dict[str, ClassDescription] = {}
    for cls, payload in data["entries"].items():
        entries[cls] = ClassDescription(
            class_name=cls,
            url_template=payload.get("url_template"),
            description=payload.get("description") or "",
        )
    return ClassCatalog(entries=entries)
