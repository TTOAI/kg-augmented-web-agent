"""V1.b — LLM annotation for all collected pages (Group M + Group L).

Purpose: 수집된 모든 페이지의 AXTree dump를 LLM에 주고 class + reason 생성.
이후 V1.c에서 convention 적용 + 사용자 검토·확정.

V1 초반에는 Group M(수동) vs Group L(LLM) 구분이 있었으나, 전체를 LLM 통과 후
연구자 review하는 workflow로 통일 — 그룹 구분 해체.

Output: output/validation/V1_pages/all_llm_annotated.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from site_adaptive_webagent.runtime.llm import make_llm_client

INPUT_DIR = Path("output/validation/V1_pages/pages")
OUTPUT_PATH = Path("output/validation/V1_pages/all_llm_annotated.json")


SYSTEM_PROMPT = """You are classifying GitLab web pages into page classes based on their AXTree structure.

Given a page's URL and AXTree dump, output:
1. A concise class name (snake_case, e.g., "issue_list", "project_main_page")
2. A short reason (1-2 sentences) explaining the class based on observable evidence:
   - URL pattern (e.g., `/-/issues` suggests issue_list)
   - Main heading text
   - Repeated sibling patterns (e.g., rows of items → list page)
   - Interactive widgets visible

Rules:
- Use snake_case.
- Prefer general class names that could apply to similar pages across projects (e.g., "issue_list" not "a11y_syntax_highlighting_issue_list").
- If the page is a list with repeated items, name it "<type>_list".
- If detail page for single entity, name it "<type>_detail" or "<type>_main".
- If a form, name it "<type>_form".

Response format: strict JSON only.
{
  "class": "<snake_case_name>",
  "reason": "<1-2 sentence reason referencing evidence>"
}
"""


def truncate_axtree(axtree, max_chars: int = 8000) -> str:
    """Truncate AXTree JSON to stay within prompt budget."""
    s = json.dumps(axtree, ensure_ascii=False)
    if len(s) > max_chars:
        s = s[:max_chars] + "\n... (truncated)"
    return s


def main():
    if not INPUT_DIR.exists():
        print(f"ERROR: {INPUT_DIR} not found. Run v1_a_collect_axtrees.py first.")
        return

    llm = make_llm_client()
    if llm is None:
        print("ERROR: LLM client unavailable")
        return

    # Load existing annotations to skip already-annotated pages
    existing = {}
    if OUTPUT_PATH.exists():
        for rec in json.loads(OUTPUT_PATH.read_text(encoding="utf-8")):
            existing[rec["name"]] = rec

    results = list(existing.values())  # start from existing
    files = sorted(INPUT_DIR.glob("*.json"))
    new_files = [f for f in files if f.stem not in existing]
    print(f"Existing annotations: {len(existing)}. New to annotate: {len(new_files)}.")
    for f in new_files:
        data = json.loads(f.read_text(encoding="utf-8"))
        axtree_str = truncate_axtree(data["axtree"])
        user_msg = (
            f"URL: {data['final_url']}\n"
            f"Title: {data['title']}\n"
            f"AXTree:\n{axtree_str}\n\n"
            "Classify this page."
        )
        try:
            response = llm.complete(system=SYSTEM_PROMPT, messages=[{"role": "user", "content": user_msg}])
        except Exception as e:
            print(f"  {f.name}: ERROR {e}")
            results.append({"name": data["name"], "url": data["final_url"],
                          "llm_raw": None, "error": str(e)})
            continue
        # Parse JSON (tolerant — extract first {...} if wrapped)
        import re
        match = re.search(r"\{[^{}]*\"class\"[^{}]*\}", response, re.DOTALL)
        parsed = None
        if match:
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        if not parsed:
            try:
                parsed = json.loads(response.strip())
            except json.JSONDecodeError:
                parsed = None
        results.append({
            "name": data["name"],
            "url": data["final_url"],
            "title": data["title"],
            "llm_raw": response,
            "llm_class": parsed.get("class") if parsed else None,
            "llm_reason": parsed.get("reason") if parsed else None,
            # User fields (to be filled)
            "user_class": "",
            "user_reason": "",
            "user_reviewed": False,
        })
        print(f"  {data['name']:30s} → class={parsed.get('class') if parsed else 'PARSE_ERR':30s}")

    OUTPUT_PATH.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSaved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
