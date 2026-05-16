"""Stage A.classify — Rule을 URL에 적용해 class path 반환.

Stage A.e에서 추출한 class_rules.json을 사용.
Stage A.f에서 3,040 StatePattern에 적용할 때 재사용 가능.

사용법:
  from scripts.kg.utils.classify import load_classifier

  cls_fn = load_classifier("output/validation/rules/class_rules.json")
  result = cls_fn("<absolute URL on the target site>")
  # → "<scope>/<class_base>" 또는 None (rule 미매칭)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from site_adaptive_webagent.kg.seed.manual_config import load_site_config
from site_adaptive_webagent.kg.types import IdentityParam, StatePattern
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

    For Stage A.f: map each StatePattern.url_template (containing slots like
    `{namespace}`) to a class. We emit a representative URL from the template,
    then classify.

     placeholder 치환값을 `config/sites/<site>/entities.yaml`
    의 `sample_values`에서 로드.
    """
    import os
    import re

    from site_adaptive_webagent.kg.site_extras import load_site_crawl, load_site_entities

    site_name = os.getenv("SITE_NAME", "gitlab")
    entities = load_site_entities(site_name)
    crawl = load_site_crawl(site_name)
    samples = entities.sample_values

    def _sample(key: str, default: str = "placeholder") -> str:
        return samples.get(key, default)

    filled = url_template
    filled = re.sub(r"\{namespace\}", _sample("namespace"), filled)
    # {project} 또는 {project_path} 둘 다 매치
    filled = re.sub(r"\{project(_path)?\}", _sample("project"), filled)
    filled = re.sub(r"\{username\}", _sample("username"), filled)
    # {branch} 또는 {branch_path}
    filled = re.sub(r"\{branch(_path)?\}", _sample("branch"), filled)
    filled = re.sub(r"\{id\}", _sample("id", "1"), filled)
    filled = re.sub(r"\{sha\}", _sample("sha"), filled)
    filled = re.sub(r"\{tag_name\}", _sample("tag_name"), filled)
    # Fallback: any remaining {xxx} → samples.get("fallback", "placeholder")
    filled = re.sub(r"\{[^}]+\}", _sample("fallback", "placeholder"), filled)
    classify = load_classifier(rules_path, site_config_path)
    base_url = crawl.base_url
    if not base_url:
        raise ValueError(
            f"crawl.base_url not configured for site={site_name!r}. "
            f"Set it in config/sites/{site_name}/crawl.yaml."
        )
    return classify(base_url + filled)


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
