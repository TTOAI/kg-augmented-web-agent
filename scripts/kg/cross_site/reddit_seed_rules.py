"""Manually-seeded Reddit (Postmill) class rules.

 cross-site 실증용. GitLab은 57개 annotation에서 자동 도출한
class_rules.json을 쓰지만, reddit은 annotation이 없으므로 Postmill URL 스키마
기반으로 주요 class 20여개를 수동 seed한다. 이는 GitLab workflow의 annotation
단계에 해당 — "수동 작업"은 새 site 적용의 고유 비용으로 인정된다.

Generated class_rules.json은 stage_a_extract_rules.py가 만드는 것과 동일한
schema를 따른다.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

# (class_name, url_template, path_params_dict, variant_queries)
RULES = [
    # Global / landing pages
    ("global/home", "/", {}, None),
    ("global/all_hot", "/all/hot", {}, None),
    ("global/all_new", "/all/new", {}, None),
    ("global/featured", "/featured/hot", {}, None),
    ("global/forums", "/forums", {}, None),
    ("global/comments", "/comments", {}, None),
    ("global/wiki", "/wiki", {}, None),
    ("global/search", "/search", {}, None),
    ("global/submit", "/submit", {}, None),
    ("global/login", "/login", {}, None),
    ("global/registration", "/registration", {}, None),
    # Forum pages (listing variants sharing family)
    ("forum/page", "/f/{forum}", {"forum": {"type": "segment"}}, None),
    ("forum/hot", "/f/{forum}/hot", {"forum": {"type": "segment"}}, None),
    ("forum/new", "/f/{forum}/new", {"forum": {"type": "segment"}}, None),
    ("forum/top", "/f/{forum}/top", {"forum": {"type": "segment"}}, None),
    ("forum/controversial", "/f/{forum}/controversial", {"forum": {"type": "segment"}}, None),
    ("forum/submit", "/f/{forum}/submit", {"forum": {"type": "segment"}}, None),
    # Post detail + comment permalink
    (
        "forum/post_detail",
        "/f/{forum}/{id}/{slug}",
        {"forum": {"type": "segment"}, "id": {"type": "segment"}, "slug": {"type": "segment"}},
        None,
    ),
    # User pages
    ("user/profile", "/user/{username}", {"username": {"type": "segment"}}, None),
    ("user/comments", "/user/{username}/comments", {"username": {"type": "segment"}}, None),
    ("user/submissions", "/user/{username}/submissions", {"username": {"type": "segment"}}, None),
    ("user/edit_biography", "/user/{username}/edit_biography", {"username": {"type": "segment"}}, None),
    # Wiki
    (
        "wiki/page",
        "/wiki/{page_path}",
        {"page_path": {"type": "path_segments"}},
        None,
    ),
]


OUT = Path("output/validation/rules/class_rules.json")


def make_rule(i: int, class_name: str, url_template: str, path_params: dict, variant_queries) -> dict:
    # specificity: literal segment count × 10 + inverse path_param count (rough)
    segs = url_template.strip("/").split("/")
    literal_count = sum(1 for s in segs if not (s.startswith("{") and s.endswith("}")))
    specificity = literal_count * 10 + max(0, 10 - len(path_params))
    return {
        "class": class_name,
        "url_template": url_template,
        "path_params": path_params,
        "variant_queries": variant_queries,
        "specificity": specificity,
        "frozen_kg_template_id": None,
        "source_instances": [f"reddit_seed_{i}"],
        "is_variant_base": False,
    }


def main() -> None:
    rules = [make_rule(i, *r) for i, r in enumerate(RULES)]
    payload = {
        "protocol_version": "2.0",
        "date": datetime.now(timezone.utc).isoformat(),
        "total_rules": len(rules),
        "self_validation": {"coverage": "manual seed — validated via stage_a_classify smoke"},
        "rules": rules,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {OUT} ({len(rules)} rules)")


if __name__ == "__main__":
    main()
