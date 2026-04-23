"""Stage A.f cluster — unmatched URL을 path pattern으로 clustering.

Input: output/validation/stage_a_f/classified.json
Output:
  output/validation/stage_a_f/iter2_unmatched_clusters.json
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse, parse_qs

CLASSIFIED_PATH = Path("output/validation/stage_a_f/classified.json")
OUT_PATH = Path("output/validation/stage_a_f/iter2_unmatched_clusters.json")

# Site-specific entity sets for normalization (TODO: externalize for multi-site)
KNOWN_NAMESPACES = {
    "byteblaze", "a11yproject", "the-a11y-project", "thoughtbot",
}
KNOWN_USERNAMES = {"byteblaze"}


def normalize_path_to_pattern(path: str) -> str:
    """URL path → cluster key.

    - Numeric IDs → {id}
    - 40-hex SHAs → {sha}
    - {namespace}/{project} detected
    - Branch placeholders after /tree/, /commits/, /blob/, /graphs/, /network/
    - tag name after /tags/
    """
    segs = [s for s in path.strip("/").split("/") if s]
    if not segs:
        return "/"

    out: list[str] = []
    i = 0

    # Detect namespace/project at front
    if len(segs) >= 2 and segs[0] == "users" and segs[1]:
        out.extend(["users", "{username}"])
        i = 2
    elif len(segs) >= 2 and segs[0] in KNOWN_NAMESPACES:
        out.extend(["{ns}", "{proj}"])
        i = 2
    elif len(segs) == 1 and segs[0] in KNOWN_USERNAMES:
        out.append("{username}")
        return "/" + "/".join(out)
    # Heuristic: detect generic namespace/project — if first two segs are both non-reserved and no '-'
    elif (len(segs) >= 2
          and segs[0] not in ("dashboard", "explore", "help", "admin", "groups",
                               "projects", "snippets", "search", "users", "-",
                               "assets", "favicon.ico")
          and segs[1] != "-"
          and "." not in segs[0]
          and "." not in segs[1]):
        # Likely namespace/project
        out.extend(["{ns}", "{proj}"])
        i = 2

    while i < len(segs):
        seg = segs[i]
        prev = segs[i - 1] if i > 0 else None
        # SHA
        if re.fullmatch(r"[0-9a-f]{8,40}", seg):
            out.append("{sha}")
        # Numeric ID
        elif re.fullmatch(r"\d+", seg):
            out.append("{id}")
        # Branch after /tree/ /commits/ /blob/ /graphs/ /network/ /raw/
        elif prev in ("tree", "commits", "blob", "graphs", "network", "raw"):
            out.append("{branch}")
            # For tree/blob/raw, rest is path
            if prev in ("tree", "blob", "raw") and i + 1 < len(segs):
                out.append("{path*}")
                break
        # Tag name
        elif i >= 2 and prev == "tags" and segs[i - 2] == "-" and seg != "new":
            out.append("{tag_name}")
        # Topic name
        elif prev == "topics" and i >= 2 and segs[i - 2] == "projects":
            out.append("{topic_name}")
        # File name extensions (index.md, etc.)
        elif re.fullmatch(r"[\w.-]+\.(md|html|rb|py|js|json|css|png|jpg|svg)", seg):
            out.append("{file}")
        else:
            out.append(seg)
        i += 1
    return "/" + "/".join(out)


def main():
    data = json.loads(CLASSIFIED_PATH.read_text(encoding="utf-8"))
    unmatched = [r for r in data if not r.get("final_class")]
    print(f"Unmatched URLs: {len(unmatched)}")

    clusters: dict[str, list[dict]] = defaultdict(list)
    for r in unmatched:
        u = r.get("final_url") or r["url"]
        p = urlparse(u)
        key = normalize_path_to_pattern(p.path)
        # Include variant-like queries as part of cluster key (e.g., ?state=done)
        q = parse_qs(p.query)
        variant_keys = ["state", "scope", "filter", "personal"]
        vq_part = ""
        for k in variant_keys:
            if k in q:
                vq_part += f"?{k}={q[k][0]}"
        clusters[key + vq_part].append({
            "url": u,
            "title": (r.get("title") or "")[:80],
            "depth": r.get("depth"),
            "linked_from": r.get("linked_from"),
        })

    # Sort by frequency desc
    sorted_clusters = sorted(clusters.items(), key=lambda x: -len(x[1]))

    # Build output
    result = []
    for pattern, records in sorted_clusters:
        # Pick up to 3 representatives (first 3 distinct URLs)
        reps = []
        seen = set()
        for rec in records:
            if rec["url"] not in seen:
                seen.add(rec["url"])
                reps.append(rec)
                if len(reps) >= 3:
                    break
        result.append({
            "pattern": pattern,
            "count": len(records),
            "representatives": reps,
        })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({
        "total_unmatched": len(unmatched),
        "total_clusters": len(result),
        "clusters": result,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    # Console summary
    print(f"Total clusters: {len(result)}")
    print()
    print("Top 30 clusters by frequency:")
    print(f"{'count':>6}  pattern")
    for c in result[:30]:
        print(f"{c['count']:>6}  {c['pattern']}")
    print()
    # Low-freq summary
    low_freq = sum(1 for c in result if c["count"] < 3)
    print(f"Low-frequency clusters (<3 count): {low_freq}")
    print(f"Saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
