"""CDIP Step 1 within-step compression for reddit.

Pipeline (CDIP v0.2 — within-step compression):
  1. Load reddit unmatched cluster representatives (from cluster_reps.json)
  2. Collect AXTree via Playwright for size >= 2 clusters (meaningful patterns)
  3. LLM annotate each rep with gpt-5.4-full (site-agnostic prompt)
  4. Merge LLM class labels into class_rules.json
  5. Re-classify full crawl pool, measure coverage
  6. Repeat from step 1 if new unmatched clusters emerge (automatic convergence)

Output:
  - output/validation_reddit_cdip/axtrees/*.json
  - output/validation_reddit_cdip/llm_annotations.json
  - output/validation/rules/class_rules.json  (final merged)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()
os.environ["OPENAI_MODEL"] = "gpt-5.4"  # full = no suffix variant

from kg_augmented_webagent.kg.site_extras import load_site_entities
from kg_augmented_webagent.kg.site_plugin import load_site_plugin
from kg_augmented_webagent.runtime.llm import make_llm_client
from scripts.kg.utils.classify import load_classifier

REDDIT_SITE = "reddit"
AXTREE_DIR = Path("output/validation_reddit_cdip/axtrees")
ANNOT_PATH = Path("output/validation_reddit_cdip/llm_annotations.json")
RULES_PATH = Path("output/validation/rules/class_rules.json")
SITE_CONFIG = Path(f"config/sites/{REDDIT_SITE}/site_config.yaml")
STORAGE_STATE = Path("output/validation/.storage_state.json")

MIN_CLUSTER_SIZE = 2  # only annotate patterns observed ≥ 2x


SYSTEM_PROMPT = """You are classifying web pages of the Postmill (Reddit-like) site into page classes based on their AXTree structure.

Given a page's URL and AXTree dump, output a concise class name (snake_case) + short reason.

Naming conventions (CDIP v0.6 — site-agnostic):
- Use scope/family_type format. Examples: "forum/post_detail", "user/profile", "global/search", "wiki/page".
- Prefer general names that apply to similar pages across forums/users (not "books_post_detail", just "post_detail").
- List pages: "<thing>_list" (e.g. "comment_list").
- Detail pages: "<thing>_detail" or "<thing>_view".
- Edit forms: "<thing>_edit".
- Sort/filter variants: base_name + suffix (e.g. "post_list_hot", "post_list_new").

Scopes (observed in Postmill):
- forum/*: pages under /f/<forum>/...
- user/*: pages under /user/<username>/...
- wiki/*: pages under /wiki/...
- global/*: top-level (/, /all/hot, /forums, /comments, /search, /submit, /login, /messages).

Output strict JSON only:
{"class": "<scope/snake_case>", "reason": "<1-2 sentence evidence>"}
"""


_STRUCTURE_EXTRACT_JS = r"""
() => {
    const INTERACTIVE = new Set([
        'a','button','input','select','textarea','form',
        'nav','main','header','footer','aside','section','article',
        'h1','h2','h3','h4','h5','h6',
        'ul','ol','li','table','tr','td','th',
    ]);
    function roleOf(el){ const r=el.getAttribute('role'); return r||el.tagName.toLowerCase(); }
    function labelOf(el){
        const aria=(el.getAttribute('aria-label')||'').trim(); if(aria) return aria;
        const alt=(el.getAttribute('alt')||'').trim(); if(alt) return alt;
        const title=(el.getAttribute('title')||'').trim(); if(title) return title;
        const txt=(el.innerText||el.textContent||'').trim();
        if(txt.length>0 && txt.length<100) return txt;
        const href=el.getAttribute('href'); if(href) return `[href: ${href}]`;
        return '';
    }
    function walk(el, depth){
        if(!el||depth>20) return null;
        const tag=el.tagName?el.tagName.toLowerCase():'';
        if(!INTERACTIVE.has(tag) && depth>0 && el.children.length===0) return null;
        const node={role:roleOf(el),label:labelOf(el).slice(0,100),children:[]};
        for(const c of el.children){ const s=walk(c,depth+1); if(s) node.children.push(s); }
        if(!INTERACTIVE.has(tag) && node.children.length===0 && !node.label) return null;
        return node;
    }
    return walk(document.body, 0);
}
"""


def truncate_axtree(tree, max_chars: int = 6000) -> str:
    s = json.dumps(tree, ensure_ascii=False)
    return s[:max_chars] + ("\n... (truncated)" if len(s) > max_chars else "")


async def collect_axtree(page, name: str, url: str) -> dict | None:
    try:
        resp = await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(1000)
        tree = await page.evaluate(_STRUCTURE_EXTRACT_JS)
        data = {
            "name": name,
            "url": url,
            "final_url": page.url,
            "title": await page.title(),
            "http_status": resp.status if resp else None,
            "axtree": tree,
        }
        AXTREE_DIR.mkdir(parents=True, exist_ok=True)
        (AXTREE_DIR / f"{name}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return data
    except Exception as e:
        print(f"  [{name}] collect ERROR: {e}")
        return None


def cluster_unmatched(rules_path: Path) -> list[dict]:
    """Re-classify with current rules, cluster unmatched, pick reps."""
    classify = load_classifier(rules_path=rules_path, site_config_path=SITE_CONFIG)
    plugin = load_site_plugin(REDDIT_SITE)
    entities = load_site_entities(REDDIT_SITE)
    crawled = json.load(open("output/validation/stage_a_f/crawled_urls.json"))

    from collections import defaultdict
    clusters = defaultdict(list)
    for r in crawled:
        if classify(r["url"]):
            continue
        path = urlparse(r["url"]).path
        q = urlparse(r["url"]).query
        segs = path.strip("/").split("/")
        tpl, params = plugin.derive_path_template(segs, entities=entities)
        qkeys = tuple(sorted(parse_qs(q).keys())) if q else ()
        key = (tpl, qkeys)
        clusters[key].append(r)

    reps = []
    for (tpl, qkeys), records in sorted(clusters.items(), key=lambda x: -len(x[1])):
        if len(records) < MIN_CLUSTER_SIZE:
            continue
        reps.append({
            "template": tpl,
            "qkeys": list(qkeys),
            "cluster_size": len(records),
            "rep_url": records[0]["url"],
            "rep_params": plugin.derive_path_template(
                urlparse(records[0]["url"]).path.strip("/").split("/"),
                entities=entities,
            )[1],
        })
    return reps, len(crawled) - sum(len(v) for v in clusters.values())


async def llm_annotate_batch(reps: list[dict], existing: dict) -> dict:
    llm = make_llm_client()
    if llm is None:
        raise RuntimeError("LLM client unavailable")
    results = dict(existing)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx_kwargs = {}
        if STORAGE_STATE.exists():
            ctx_kwargs["storage_state"] = str(STORAGE_STATE)
        ctx = await browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()
        page.set_default_timeout(30000)
        for i, rep in enumerate(reps):
            name = f"c{i:03d}_" + re.sub(r"[^a-zA-Z0-9]", "_", rep["template"].strip("/"))[:50]
            if name in results:
                continue
            # Collect AXTree
            data = await collect_axtree(page, name, rep["rep_url"])
            if not data or not data.get("axtree"):
                continue
            ax_str = truncate_axtree(data["axtree"])
            qsig = "?" + ",".join(rep["qkeys"]) if rep["qkeys"] else ""
            user_msg = (
                f"URL: {data['final_url']}\n"
                f"Title: {data['title']}\n"
                f"Cluster template: {rep['template']}{qsig} (observed {rep['cluster_size']}x)\n"
                f"AXTree:\n{ax_str}\n\n"
                "Classify this page."
            )
            try:
                response = llm.complete(system=SYSTEM_PROMPT, messages=[{"role": "user", "content": user_msg}])
            except Exception as e:
                print(f"  [{name}] LLM ERROR: {e}")
                continue
            # Parse JSON
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
            cls = parsed.get("class") if parsed else None
            reason = parsed.get("reason") if parsed else None
            results[name] = {
                "name": name,
                "url": data["final_url"],
                "title": data["title"],
                "template": rep["template"],
                "qkeys": rep["qkeys"],
                "cluster_size": rep["cluster_size"],
                "params": rep["rep_params"],
                "user_class": cls,
                "user_reason": reason,
                "llm_raw": response,
            }
            ANNOT_PATH.parent.mkdir(parents=True, exist_ok=True)
            ANNOT_PATH.write_text(
                json.dumps(list(results.values()), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"  [{name}] → {cls}  ({rep['cluster_size']}x {rep['template']}{qsig})")
        await browser.close()
    return results


def merge_annotations_to_rules(annots: dict) -> None:
    """Add LLM-annotated classes as rules (skip if template/class already present)."""
    current = json.load(open(RULES_PATH))
    existing_templates = {r["url_template"] for r in current["rules"]}
    existing_classes = {r["class"] for r in current["rules"]}
    added = 0
    for rec in annots.values():
        cls = rec.get("user_class")
        tpl = rec.get("template")
        if not cls or not tpl:
            continue
        if tpl in existing_templates:
            continue
        # Ensure unique class name
        if cls in existing_classes:
            cls_orig = cls
            n = 2
            while cls in existing_classes:
                cls = f"{cls_orig}_{n}"
                n += 1
        existing_classes.add(cls)
        # Specificity = literal segment count × 10
        lit = sum(1 for s in tpl.strip("/").split("/") if not (s.startswith("{") and s.endswith("}")))
        current["rules"].append({
            "class": cls,
            "url_template": tpl,
            "path_params": rec.get("params") or {},
            "variant_queries": None,
            "specificity": lit * 10,
            "frozen_kg_template_id": None,
            "source_instances": [rec["name"]],
            "is_variant_base": False,
        })
        added += 1
    current["total_rules"] = len(current["rules"])
    RULES_PATH.write_text(json.dumps(current, indent=2, ensure_ascii=False))
    print(f"Added {added} rules via LLM annotation (total: {current['total_rules']})")


async def main():
    for cycle in range(3):  # max 3 compression cycles
        print(f"\n===== CDIP compression cycle {cycle + 1} =====")
        reps, matched_count = cluster_unmatched(RULES_PATH)
        print(f"Unmatched clusters (size >= {MIN_CLUSTER_SIZE}): {len(reps)}")
        if not reps:
            print("No more clusters to annotate — convergence reached.")
            break
        existing_annots = {}
        if ANNOT_PATH.exists():
            existing_annots = {r["name"]: r for r in json.loads(ANNOT_PATH.read_text())}
        annots = await llm_annotate_batch(reps, existing_annots)
        # Apply + reclassify
        pre_count = json.load(open(RULES_PATH))["total_rules"]
        merge_annotations_to_rules(annots)
        post_count = json.load(open(RULES_PATH))["total_rules"]
        new_rules_added = post_count - pre_count
        if new_rules_added == 0:
            print("No new rules added — convergence (within-step).")
            break
    print("\n===== CDIP compression done =====")


if __name__ == "__main__":
    asyncio.run(main())
