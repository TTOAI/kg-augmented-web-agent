"""Stage A.classify — Rule을 URL에 적용해 class path 반환.

Stage A.e에서 추출한 class_rules.json을 사용.
Stage A.f에서 3,040 StatePattern에 적용할 때 재사용 가능.

사용법:
  from scripts.validation.stage_a_classify import load_classifier

  cls_fn = load_classifier("output/validation/rules/class_rules.json")
  result = cls_fn("http://localhost:8023/byteblaze/a11y-syntax-highlighting/-/issues")
  # → "project/issue_list"
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from site_adaptive_webagent.kg.seed.manual_config import load_site_config
from site_adaptive_webagent.kg.types import IdentityParam, SiteConfig, StatePattern
from site_adaptive_webagent.kg.urlnorm import match_pattern

DEFAULT_SITE_CONFIG = Path("config/sites/gitlab/site_config.yaml")
DEFAULT_RULES_PATH = Path("output/validation/rules/class_rules.json")


def _build_state_pattern(rule: dict) -> StatePattern:
    idparams = []
    if rule.get("variant_queries"):
        vq = rule["variant_queries"]
        idparams.append(IdentityParam(name=vq["key"], type="string", required=False, default=None))
    return StatePattern(
        id=f"rule:{rule['class']}",
        url_template=rule["url_template"],
        path_params=rule.get("path_params", {}),
        identity_query_params=idparams,
    )


def load_classifier(
    rules_path: str | Path = DEFAULT_RULES_PATH,
    site_config_path: str | Path = DEFAULT_SITE_CONFIG,
) -> Callable[[str], str | None]:
    """Return a closure `fn(url) → class_path | None`."""
    data = json.loads(Path(rules_path).read_text(encoding="utf-8"))
    rules = data["rules"]
    rules.sort(key=lambda r: -r["specificity"])
    site_config = load_site_config(site_config_path)

    patterns = [(r, _build_state_pattern(r)) for r in rules]

    def classify(url: str) -> str | None:
        for rule, pattern in patterns:
            ok, bindings = match_pattern(url, pattern, site_config)
            if not ok:
                continue
            base_class = rule["class"]
            vq = rule.get("variant_queries")
            if vq:
                key = vq["key"]
                val = bindings.get(key)
                val_key = str(val) if val is not None else "__absent__"
                variant = vq["mapping"].get(val_key) or vq["mapping"].get("__absent__")
                if variant:
                    return f"{base_class}/{variant}"
            return base_class
        return None

    return classify


def classify_template(
    url_template: str,
    rules_path: str | Path = DEFAULT_RULES_PATH,
    site_config_path: str | Path = DEFAULT_SITE_CONFIG,
) -> str | None:
    """Classify a URL template (as used in Frozen KG StatePattern).

    For Stage A.f: map each StatePattern.url_template (containing slots like {namespace})
    to a class. We emit a representative URL from the template, then classify.
    """
    # Fill slots with plausible placeholders that our rules accept.
    # Use known namespace/project/etc. so heuristics catch them.
    import re
    filled = url_template
    filled = re.sub(r"\{namespace\}", "byteblaze", filled)
    filled = re.sub(r"\{project(_path)?\}", "a11y-syntax-highlighting", filled)
    filled = re.sub(r"\{username\}", "byteblaze", filled)
    filled = re.sub(r"\{branch\}", "main", filled)
    filled = re.sub(r"\{id\}", "1", filled)
    filled = re.sub(r"\{sha\}", "62820763d9b5f3b25720596f542aaf89d917fb17", filled)
    filled = re.sub(r"\{tag_name\}", "v0.1.0", filled)
    # Fallback: any remaining {xxx} → "placeholder"
    filled = re.sub(r"\{[^}]+\}", "placeholder", filled)
    classify = load_classifier(rules_path, site_config_path)
    return classify("http://localhost:8023" + filled)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: stage_a_classify.py <url>")
        sys.exit(1)
    url = sys.argv[1]
    classify = load_classifier()
    result = classify(url)
    print(f"{url}")
    print(f"  → {result}")
