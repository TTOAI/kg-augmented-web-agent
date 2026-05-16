"""3-source SiteKG diff helper — 수동 검증 보조.

manual / crawl / derived(llm) SiteKG 간 항목별 비교 결과를 markdown 표로 생성.
사람이 이를 보면서 config/sites/<site>/{infotypes.yaml, kg_seed.json}을 직접
편집해 승격·강등을 반영. 자동 변경은 하지 않는다.

비교 key는 store._merge_edges와 동일한 함수를 재사용해 일관성 확보.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..types import LeadsToEdge, RealizesEdge, SiteKG


@dataclass(slots=True)
class DiffEntry:
    """단일 항목의 source 별 존재 여부."""

    key: str  # display key
    in_manual: bool
    in_crawl: bool
    in_llm: bool
    detail: str = ""  # url_template / description 등


def diff_state_patterns(
    manual: SiteKG, crawl: SiteKG, llm: SiteKG,
) -> list[DiffEntry]:
    keys = sorted(set(manual.state_patterns) | set(crawl.state_patterns) | set(llm.state_patterns))
    out: list[DiffEntry] = []
    for k in keys:
        m = manual.state_patterns.get(k)
        c = crawl.state_patterns.get(k)
        l = llm.state_patterns.get(k)
        templates = {x.url_template for x in (m, c, l) if x is not None}
        detail = "; ".join(sorted(templates))
        out.append(DiffEntry(key=k, in_manual=m is not None, in_crawl=c is not None, in_llm=l is not None, detail=detail))
    return out


def diff_actions(
    manual: SiteKG, crawl: SiteKG, llm: SiteKG,
) -> list[DiffEntry]:
    keys = sorted(set(manual.actions) | set(crawl.actions) | set(llm.actions))
    out: list[DiffEntry] = []
    for k in keys:
        m = manual.actions.get(k)
        c = crawl.actions.get(k)
        l = llm.actions.get(k)
        descriptions = {(x.description or "").strip() for x in (m, c, l) if x is not None and (x.description or "").strip()}
        detail = "; ".join(sorted(descriptions))[:120]
        out.append(DiffEntry(key=k, in_manual=m is not None, in_crawl=c is not None, in_llm=l is not None, detail=detail))
    return out


def diff_realizes_edges(
    manual: SiteKG, crawl: SiteKG, llm: SiteKG,
) -> list[DiffEntry]:
    keyed = {}
    for source, kg in (("manual", manual), ("crawl", crawl), ("llm", llm)):
        for e in kg.realizes_edges:
            k = _realizes_key(e)
            entry = keyed.setdefault(k, {"manual": False, "crawl": False, "llm": False})
            entry[source] = True
    out: list[DiffEntry] = []
    for k in sorted(keyed):
        v = keyed[k]
        out.append(
            DiffEntry(
                key=f"{k[0]} ──({k[2]})──> {k[1]}",
                in_manual=v["manual"], in_crawl=v["crawl"], in_llm=v["llm"],
            )
        )
    return out


def diff_leads_to_edges(
    manual: SiteKG, crawl: SiteKG, llm: SiteKG,
) -> list[DiffEntry]:
    keyed = {}
    for source, kg in (("manual", manual), ("crawl", crawl), ("llm", llm)):
        for e in kg.leads_to_edges:
            k = _leads_to_key(e)
            entry = keyed.setdefault(k, {"manual": False, "crawl": False, "llm": False})
            entry[source] = True
    out: list[DiffEntry] = []
    for k in sorted(keyed):
        v = keyed[k]
        out.append(
            DiffEntry(
                key=f"{k[0]} --[{k[1]}]--> {k[2]}",
                in_manual=v["manual"], in_crawl=v["crawl"], in_llm=v["llm"],
            )
        )
    return out


def render_markdown(
    manual: SiteKG, crawl: SiteKG, llm: SiteKG,
) -> str:
    """3-source diff 전체를 markdown 표로 직렬화."""
    lines: list[str] = []
    lines.append(f"# KG 3-source diff — site={manual.site or crawl.site or llm.site}")
    lines.append("")
    lines.append("Source 표시: ✓=존재, -=부재. 사람이 이 표를 보고 config 직접 수정.")
    lines.append("")

    sections = [
        ("StatePatterns", diff_state_patterns(manual, crawl, llm)),
        ("Actions", diff_actions(manual, crawl, llm)),
        ("RealizesEdges", diff_realizes_edges(manual, crawl, llm)),
        ("LeadsToEdges", diff_leads_to_edges(manual, crawl, llm)),
    ]
    for title, entries in sections:
        lines.append(f"## {title} (n={len(entries)})")
        if not entries:
            lines.append("_(none)_")
            lines.append("")
            continue
        lines.append("| key | manual | crawl | llm | detail |")
        lines.append("|---|---|---|---|---|")
        for e in entries:
            lines.append(
                f"| `{e.key}` | {_mark(e.in_manual)} | {_mark(e.in_crawl)} "
                f"| {_mark(e.in_llm)} | {e.detail} |"
            )
        lines.append("")
    return "\n".join(lines)


# key 함수는 store._merge_edges와 동일하게 유지해야 함
def _realizes_key(e: RealizesEdge) -> tuple[str, str, str]:
    return (e.infotype, e.state_pattern_id, e.condition)


def _leads_to_key(e: LeadsToEdge) -> tuple[str, str, str]:
    return (e.from_state_pattern_id, e.action_name, e.to_state_pattern_id)


def _mark(present: bool) -> str:
    return "✓" if present else "-"
