"""Stage B.1 — Collect per-class actions.

For each class, pick 1-3 sample URLs from the accumulated pool (step 1 + step 2').
Re-visit each sample, extract actionable elements (a[href], button, role=button).
Save raw action list per class.

Stage B.2/3 aggregate + normalize afterwards.

Input:
  output/validation/stage_a_f/classified.json (step 1, 1457)
  output/validation/stage_a_f/step/step_2_new.json (step 2', 238)
  output/validation/rules/class_rules.json

Output:
  output/validation/stage_b/raw_actions_per_class.json
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path

from playwright.async_api import async_playwright

from scripts.kg.utils.classify import load_classifier
from scripts.kg.build.crawl import BASE_URL, STORAGE_STATE

POOL_PATHS = [
    Path("output/validation/stage_a_f/classified.json"),
    Path("output/validation/stage_a_f/step/step_2_new.json"),
]
OUT = Path("output/validation/stage_b/raw_actions_per_class.json")

SAMPLES_PER_CLASS = 3  # up to N sample URLs per class
DELAY_MS = 120

ACTION_EXTRACT_JS = r"""
() => {
    const els = Array.from(document.querySelectorAll(
        'a[href], button, [role="button"], [role="tab"], [role="link"], input[type="submit"]'
    ));
    const out = [];
    for (const e of els) {
        if (e.offsetParent === null) continue;
        const label = (e.innerText || e.getAttribute('aria-label') || e.getAttribute('title') || '').trim().replace(/\s+/g, ' ');
        if (!label || label.length > 120) continue;
        const tag = e.tagName.toLowerCase();
        const href = e.getAttribute('href') || null;
        const role = e.getAttribute('role') || null;
        const type = e.getAttribute('type') || null;
        out.push({label, tag, href, role, type});
    }
    return out;
}
"""

#   MUTATE form shortcut — DOM의 <form> 요소 + 그 아래 input/select/textarea
# 메타데이터를 수집해 agent에게 "POST/PUT endpoint + required params" 힌트로 제공.
# 각 form의 action / method / field list를 JSON으로 덤프.
#
# 수집 범위:
#   - action (form submission URL, 절대 경로로 변환)
#   - method (POST/GET/PATCH/DELETE 등; 'dialog' 등 특수값은 무시)
#   - fields: name/type/required/default/placeholder/checked/options(select)
#
# 보안/운영 고려:
#   - authenticity_token / _method hidden 은 agent에게는 "런타임 추출" 대상이라 힌트에서 제외
#   - password / session / OTP 필드는 민감하므로 placeholder만 노출 (value 제외)
FORM_EXTRACT_JS = r"""
() => {
    const SENSITIVE_NAMES = new Set([
        'password', 'current_password', 'new_password', 'password_confirmation',
        'otp', 'one_time_password', 'code',
    ]);
    const EXCLUDED_NAMES = new Set([
        'authenticity_token', 'utf8', '_method',
    ]);
    function normalizeUrl(action) {
        if (!action) return location.pathname + location.search;
        try {
            const u = new URL(action, location.href);
            if (u.origin === location.origin) return u.pathname + u.search;
            return action;
        } catch (_) { return action; }
    }
    const forms = document.querySelectorAll('form');
    const out = [];
    for (const f of forms) {
        const rawMethod = (f.getAttribute('method') || 'GET').toUpperCase();
        const actionUrl = normalizeUrl(f.getAttribute('action') || f.action || '');
        // HTTP method override via hidden <input name="_method">
        const mOverride = f.querySelector('input[name="_method"]');
        const method = mOverride ? (mOverride.value || rawMethod).toUpperCase() : rawMethod;
        if (method === 'DIALOG') continue;
        // Collect fields
        const fields = [];
        const inputs = f.querySelectorAll('input, select, textarea');
        for (const el of inputs) {
            const name = el.getAttribute('name') || '';
            if (!name || EXCLUDED_NAMES.has(name)) continue;
            const tag = el.tagName.toLowerCase();
            const type = (el.getAttribute('type') || tag).toLowerCase();
            const required = el.required || el.hasAttribute('required');
            const placeholder = el.getAttribute('placeholder') || '';
            const isSensitive = SENSITIVE_NAMES.has(name) || type === 'password';
            const fieldEntry = {
                name, tag, type,
                required,
                placeholder: placeholder.slice(0, 80),
            };
            // default value (except sensitive)
            if (!isSensitive) {
                if (tag === 'select') {
                    const selected = el.querySelector('option[selected]') || el.querySelector('option');
                    fieldEntry.default_value = selected ? (selected.value || selected.textContent.trim()).slice(0, 80) : '';
                    // Collect option values (up to 10)
                    const opts = Array.from(el.querySelectorAll('option')).slice(0, 10).map(o => ({
                        value: (o.value || '').slice(0, 60),
                        label: (o.textContent || '').trim().slice(0, 60),
                    }));
                    fieldEntry.options = opts;
                } else if (type === 'radio') {
                    fieldEntry.default_value = el.value || '';
                    fieldEntry.checked = !!el.checked;
                } else if (type === 'checkbox') {
                    fieldEntry.default_value = el.value || '1';
                    fieldEntry.checked = !!el.checked;
                } else if (type === 'hidden') {
                    fieldEntry.default_value = (el.value || '').slice(0, 80);
                } else {
                    fieldEntry.default_value = (el.value || '').slice(0, 80);
                }
            } else {
                fieldEntry.sensitive = true;
            }
            fields.push(fieldEntry);
        }
        // Submit button label (if any) — helps agent identify form purpose
        let submitLabel = '';
        const btn = f.querySelector('button[type="submit"], input[type="submit"]');
        if (btn) {
            submitLabel = (btn.innerText || btn.getAttribute('value') || btn.getAttribute('aria-label') || '').trim().slice(0, 60);
        }
        out.push({action: actionUrl, method, submit_label: submitLabel, fields});
    }
    return out;
}
"""

# role=tab 요소의 href가 '#' 또는 null일 때 Playwright 클릭으로 URL
# 변화를 관측해 실제 쿼리 파라미터 포함 URL을 캡처한다. ARIA 계약상 role="tab"은
# 읽기 전용 view switch이므로 side effect 없음 (state 변경 없는 filter URL 요청).
# Click 후 `goto(original)`로 복원.
TAB_CAPTURE_LIMIT = 10  # per URL, avoid runaway when page has many stale tabs
DROPDOWN_CAPTURE_LIMIT = 15  # per URL, number of distinct filter toggles we enumerate
DROPDOWN_OPTION_LIMIT = 30  # per toggle, number of options we retain (top-N)


# Enumerate static dropdown options already rendered in the DOM without any
# click (works for <select>, aria-controls listbox pre-rendered, role=menu with
# visibility-hidden). Hidden-but-rendered options remain in the DOM tree even
# when collapsed, so we can scrape them as filter metadata without triggering
# any state change.
STATIC_DROPDOWN_EXTRACT_JS = r"""
() => {
    const out = [];
    function record(toggleEl, menuEl) {
        const label = ((toggleEl.innerText || toggleEl.getAttribute('aria-label') || '') + '').trim().replace(/\s+/g, ' ').slice(0, 80);
        if (!label) return;
        const opts = [];
        const optEls = menuEl.querySelectorAll('[role="menuitem"], [role="option"], [role="menuitemcheckbox"], [role="menuitemradio"], option, a[href]');
        for (const o of optEls) {
            const name = ((o.innerText || o.textContent || o.getAttribute('aria-label') || o.getAttribute('value') || '') + '').trim().replace(/\s+/g, ' ');
            if (!name || name.length > 120) continue;
            const href = o.getAttribute('href') || (o.tagName === 'OPTION' ? ('?' + (o.getAttribute('value') || '')) : null);
            opts.push({name, href});
            if (opts.length >= 30) break;
        }
        if (opts.length === 0) return;
        out.push({label, options: opts});
    }
    // 1) <select> — options are DOM children, always present.
    for (const sel of document.querySelectorAll('select[name]')) {
        const name = sel.getAttribute('name') || '';
        const toggleLabel = (sel.labels && sel.labels[0] ? sel.labels[0].innerText : '') || sel.getAttribute('aria-label') || name;
        const opts = [];
        for (const o of sel.querySelectorAll('option')) {
            const txt = ((o.innerText || o.textContent || '') + '').trim().replace(/\s+/g, ' ');
            const val = o.getAttribute('value') || '';
            if (!val && !txt) continue;
            opts.push({name: txt || val, value: val});
            if (opts.length >= 30) break;
        }
        if (!opts.length) continue;
        out.push({label: toggleLabel.trim().slice(0, 80) || name, param: name, options: opts});
    }
    // 2) aria-controls → target menu/listbox. Works even when menu is hidden
    //    as long as the target is present in DOM.
    for (const tog of document.querySelectorAll('[aria-controls][aria-haspopup], [aria-controls][role="combobox"], button[aria-controls], [data-toggle][aria-controls]')) {
        const id = tog.getAttribute('aria-controls');
        if (!id) continue;
        const menu = document.getElementById(id);
        if (!menu) continue;
        record(tog, menu);
    }
    return out;
}
"""


import re as _re

# AXTree-based filter extraction. Playwright's `page.accessibility.snapshot()`
# returns the browser's interpretation of the ARIA accessibility tree, which:
#   - includes nodes behind aria-hidden / display:none (interestingOnly=False)
#   - normalizes labels via aria-labelledby / aria-label / label-for chains
#   - handles custom component frameworks (Pajamas, Vue, React) uniformly
#     as long as they implement ARIA roles correctly
# This covers combobox / listbox / menu even when the underlying DOM uses
# bespoke class names that would miss a pure DOM-selector scan.
_AX_COMBO_ROLES = {"combobox", "listbox", "menu"}
_AX_OPTION_ROLES = {"option", "menuitem", "menuitemcheckbox", "menuitemradio", "tab"}
_AX_TRAILING_COUNT = _re.compile(r"\s+\d{1,6}$")
_AX_NEWLINE_RUN = _re.compile(r"[\n\t]+")
_AX_SPACE_RUN = _re.compile(r"\s{2,}")


def _ax_normalize_name(raw: str) -> str:
    """Normalize an accessibility `label` / `name` to a clean, clickable form.

    - Strip trailing count badges: "Open 40" → "Open"
    - Collapse composite labels split by newlines: "Import CSV\\n\\nImport from Jira"
      leaves the first segment only (individual options are captured via
      role=option children; a composite label indicates the menu-level aggregate).
    """
    if not raw:
        return ""
    text = _AX_NEWLINE_RUN.sub(" \u0000 ", raw).strip()
    if "\u0000" in text:
        text = text.split("\u0000", 1)[0].strip()
    text = _AX_SPACE_RUN.sub(" ", text)
    text = _AX_TRAILING_COUNT.sub("", text)
    return text.strip()[:80]


def _cdp_axtree_walk(nodes: list[dict], out: list[dict],
                     empty_clickables: list[dict]) -> None:
    """Walk a flat CDP AXTree (Accessibility.getFullAXTree result).

    nodes: list of {nodeId, role:{value}, name:{value}, childIds, ...}
    Emits one entry per combobox/listbox/menu/tablist whose descendant tree
    includes option/menuitem/tab children. Button nodes bearing a filter-like
    accessibility name (no child options yet) are recorded in empty_clickables
    for pass-2 click expansion.
    """
    by_id = {n["nodeId"]: n for n in nodes}
    container_roles = {"combobox", "listbox", "menu", "tablist"}
    option_roles = {"option", "menuitem", "menuitemcheckbox", "menuitemradio", "tab"}

    def descendant_options(start_id: str, budget: int = 40) -> list[str]:
        collected: list[str] = []
        stack = [start_id]
        seen = set()
        while stack and len(collected) < budget:
            nid = stack.pop()
            if nid in seen:
                continue
            seen.add(nid)
            node = by_id.get(nid)
            if not node:
                continue
            r = (node.get("role") or {}).get("value")
            nm = _ax_normalize_name((node.get("name") or {}).get("value") or "")
            if r in option_roles and nm:
                if nm not in collected:
                    collected.append(nm)
            for cid in (node.get("childIds") or []):
                stack.append(cid)
        return collected

    for node in nodes:
        role = (node.get("role") or {}).get("value")
        if role in container_roles:
            label = _ax_normalize_name((node.get("name") or {}).get("value") or "")
            opts = descendant_options(node["nodeId"])
            if opts:
                out.append({
                    "label": label or f"<{role}>",
                    "options": [{"name": o} for o in opts],
                    "_ax_role": role,
                })
        elif role == "button":
            # Capture button whose name looks like a filter toggle (hint for
            # pass-2 expansion). Pajamas / Vue dropdown buttons land here.
            label = _ax_normalize_name((node.get("name") or {}).get("value") or "")
            if not label or len(label) > 40:
                continue
            # Skip obvious non-filter buttons by keyword (create, submit, save,
            # delete, cancel). Opt-in: label must be short token.
            lw = label.lower()
            if any(s in lw for s in ("save", "create", "submit", "delete",
                                      "cancel", "confirm", "add", "edit",
                                      "close", "comment")):
                continue
            empty_clickables.append({"label": label, "nodeId": node["nodeId"]})


async def _extract_ax_filter_controls(
    page, original_url: str, max_expand: int = 6
) -> list[dict]:
    """Extract filter-control metadata from CDP accessibility tree.

    Pass 1: static CDP AXTree snapshot — captures combobox/listbox/menu/tablist
            + descendant option/menuitem/tab children.
    Pass 2: for button nodes whose label looks like a filter toggle, click to
            trigger lazy expansion, re-snapshot, and capture newly appeared
            option descendants. Escape to collapse.
    """
    results: list[dict] = []
    empty_clickables: list[dict] = []
    try:
        cdp = await page.context.new_cdp_session(page)
    except Exception:
        return results
    try:
        snap1 = await cdp.send("Accessibility.getFullAXTree")
        nodes1 = snap1.get("nodes") or []
    except Exception:
        nodes1 = []
    if nodes1:
        _cdp_axtree_walk(nodes1, results, empty_clickables)

    # Signature of pass-1 containers, so pass-2 can detect newly-appeared ones.
    def _sig(entry: dict) -> tuple:
        return (entry.get("label", ""), tuple(o["name"] for o in entry.get("options") or []))
    pass1_sigs = {_sig(e) for e in results}

    for entry in empty_clickables[:max_expand]:
        label = entry["label"]
        try:
            btn = page.get_by_role("button", name=label).first
            if await btn.count() == 0:
                continue
            try:
                await btn.click(timeout=2000)
            except Exception:
                continue
            await page.wait_for_timeout(350)
            try:
                snap2 = await cdp.send("Accessibility.getFullAXTree")
                nodes2 = snap2.get("nodes") or []
            except Exception:
                nodes2 = []
            if nodes2:
                tmp: list[dict] = []
                _cdp_axtree_walk(nodes2, tmp, [])
                for new_entry in tmp:
                    s = _sig(new_entry)
                    if s in pass1_sigs:
                        continue
                    if new_entry["label"].startswith("<") and new_entry["label"].endswith(">"):
                        new_entry["label"] = label
                    results.append(new_entry)
                    pass1_sigs.add(s)
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            if page.url != original_url:
                try:
                    await page.goto(original_url, wait_until="domcontentloaded",
                                    timeout=8000)
                except Exception:
                    break
        except Exception:
            continue

    deduped: dict[str, dict] = {}
    for e in results:
        lbl = e.get("label") or ""
        if lbl.startswith("<") and lbl.endswith(">"):
            continue
        opts = e.get("options") or []
        if not opts:
            continue
        key = lbl
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = {"label": lbl, "options": opts, "param": ""}
        else:
            seen_opts = {o["name"] for o in existing["options"]}
            for o in opts:
                if o["name"] not in seen_opts:
                    existing["options"].append(o)
                    seen_opts.add(o["name"])
    return list(deduped.values())


async def _extract_filter_categories(
    page, original_url: str, *,
    filter_category_params: dict[str, str],
    max_categories: int = 12,
) -> list[dict]:
    """Recursive 3-level expansion of a GitLab-style filtered-search input.

    Level 1: click the search/filter input → collect role=menuitem entries
             (filter categories: Label, Assignee, Author, Milestone, ...)
    Level 2: click each category → collect operators (role=menuitem), e.g.
             "=\\nis" / "!=\\nis not"
    Level 3: click the first operator → networkidle + brief wait → collect
             a few menuitem entries as **existence proof** (example values,
             not a complete inventory).

    Produces per-category entries with URL param (from filter_category_params
    config) and operators + example values. Missing categories in the config
    map yield `param=""` — still useful for agent ("filter exists").

    Site-agnostic: matches the ARIA menuitem pattern. Sites whose filter UI
    uses non-ARIA controls capture nothing (graceful).
    """
    out: list[dict] = []
    try:
        search = page.locator(
            'input[placeholder*="Search or filter" i], input[placeholder*="filter results" i]'
        ).first
        if await search.count() == 0:
            return out
    except Exception:
        return out

    async def _open_l1() -> list[str]:
        try:
            await search.click(timeout=3000)
            await page.wait_for_timeout(350)
            items = await page.evaluate(
                """() => [...document.querySelectorAll('[role="menuitem"]')]
                    .filter(e => e.offsetParent)
                    .map(e => (e.innerText || '').trim())
                    .filter(x => x && x.length < 60)"""
            )
            return items
        except Exception:
            return []

    async def _close_all() -> None:
        for _ in range(3):
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            await page.wait_for_timeout(100)
        if page.url != original_url:
            try:
                await page.goto(original_url, wait_until="domcontentloaded", timeout=8000)
            except Exception:
                pass

    categories = await _open_l1()
    if not categories:
        await _close_all()
        return out
    # Filter to configured categories first (keeps list compact), then add
    # any unmapped names as a tail so novel categories still appear with empty
    # param.
    ordered: list[str] = []
    for name in categories:
        if name in filter_category_params and name not in ordered:
            ordered.append(name)
    for name in categories:
        if name not in ordered:
            ordered.append(name)
    ordered = ordered[:max_categories]

    # GitLab filter UI has a quirk: Escape inside the operator popup can
    # advance to the value popup (L3) rather than collapsing. Robust recovery
    # requires a full page reload between categories. Cost ≈ 2s/category.
    async def _reload_and_open_search() -> bool:
        try:
            await page.goto(original_url, wait_until="domcontentloaded", timeout=10000)
            await page.wait_for_timeout(300)
            s = page.locator(
                'input[placeholder*="Search or filter" i], input[placeholder*="filter results" i]'
            ).first
            if await s.count() == 0:
                return False
            await s.click(timeout=2000)
            await page.wait_for_timeout(250)
            return True
        except Exception:
            return False

    # Phase A: for each category, reload → open search → click category →
    # read operators. Page state is clean between iterations.
    for cat in ordered:
        if not await _reload_and_open_search():
            break
        try:
            await page.get_by_role("menuitem", name=cat).first.click(timeout=2000)
        except Exception:
            continue
        await page.wait_for_timeout(250)
        try:
            operators = await page.evaluate(
                """() => [...document.querySelectorAll('[role="menuitem"]')]
                    .filter(e => e.offsetParent)
                    .map(e => (e.innerText || '').trim().replace(/\\s+/g, ' '))
                    .filter(x => x && x.length < 40)"""
            )
        except Exception:
            operators = []
        out.append({
            "name": cat,
            "param": filter_category_params.get(cat, ""),
            "operators": operators[:4],
            "example_values": [],
            "has_values": False,
        })

    # Phase B: existence proof — drill the first captured category through L3.
    await _close_all()
    for entry in out:
        ops = entry.get("operators") or []
        if not ops:
            continue
        try:
            await page.goto(original_url, wait_until="domcontentloaded", timeout=10000)
            await page.wait_for_timeout(400)
            await search.click(timeout=2000)
            await page.wait_for_timeout(200)
            await page.get_by_role("menuitem", name=entry["name"]).first.click(timeout=2000)
            await page.wait_for_timeout(200)
            op_label = ops[0].split("\n")[0].strip() or ops[0]
            await page.get_by_role("menuitem", name=op_label).first.click(timeout=2000)
            try:
                await page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                pass
            await page.wait_for_timeout(400)
            values = await page.evaluate(
                """() => [...document.querySelectorAll('[role="menuitem"]')]
                    .filter(e => e.offsetParent)
                    .map(e => (e.innerText || '').trim().replace(/\\s+/g, ' '))
                    .filter(x => x && x.length < 60)"""
            )
            if values:
                entry["has_values"] = True
                entry["example_values"] = values[:5]
        except Exception:
            pass
        break  # only drill one category

    await _close_all()
    return out


MODAL_TRIGGER_LIMIT = 8  # per URL, max number of modal triggers we try


async def _extract_modal_structures(
    page, original_url: str, max_triggers: int = MODAL_TRIGGER_LIMIT,
) -> list[dict]:
    """Collect structural info of dialog-opening interactions — ARIA only.

    Trigger = `[aria-haspopup="dialog"]` (WAI-ARIA standard).
    Dialog appearance is detected by `[role="dialog"]` + `aria-modal="true"`
    (or plain `role="dialog"` as a fallback). Sites that open dialogs via
    custom components without this ARIA annotation are out of scope; their
    dialogs are not captured. That is a property of the target site's ARIA
    conformance, not a limit of the protocol.

    Returns list of entries shaped as:
      {"trigger_label": str, "inputs": [...], "submit_labels": [str],
       "form_action": str?, "form_method": str?}
    """
    out: list[dict] = []
    try:
        triggers = page.locator('[aria-haspopup="dialog"]')
        n = await triggers.count()
    except Exception:
        return out
    n = min(n, max_triggers)
    seen_labels: set[str] = set()
    for i in range(n):
        try:
            loc = triggers.nth(i)
            if not await loc.is_visible():
                continue
            label_raw = (
                (await loc.inner_text()) or (await loc.get_attribute("aria-label")) or ""
            )
            label = label_raw.strip().replace("\n", " ")[:80]
            if not label or label in seen_labels:
                continue
            seen_labels.add(label)
            try:
                await loc.click(timeout=2000)
            except Exception:
                continue
            try:
                await page.wait_for_selector(
                    '[role="dialog"][aria-modal="true"]:visible, '
                    '[role="dialog"]:visible',
                    timeout=2500,
                )
            except Exception:
                continue
            entry = await page.evaluate(
                r"""
                () => {
                    const modal = document.querySelector(
                        '[role="dialog"][aria-modal="true"], '
                        + '[role="dialog"]:not([aria-hidden="true"])'
                    );
                    if (!modal) return null;
                    const inputs = [];
                    const els = modal.querySelectorAll(
                        'input, textarea, select, '
                        + '[role="searchbox"], [role="combobox"], [role="textbox"], [role="listbox"]'
                    );
                    for (const e of els) {
                        const tag = e.tagName.toLowerCase();
                        const role = e.getAttribute('role') || tag;
                        const type = (e.getAttribute('type') || '').toLowerCase();
                        if (type === 'hidden') continue;
                        const name = e.getAttribute('name') || '';
                        if (name.startsWith('_') || name === 'authenticity_token' || name === 'utf8') continue;
                        const ariaLabel = e.getAttribute('aria-label') || '';
                        let labelText = '';
                        const id = e.getAttribute('id');
                        if (id) {
                            const lab = modal.querySelector('label[for="' + id + '"]');
                            if (lab) labelText = (lab.innerText || '').trim();
                        }
                        const options = [];
                        if (tag === 'select') {
                            for (const o of e.querySelectorAll('option')) {
                                const t = (o.innerText || o.textContent || '').trim();
                                if (t && t.length < 60) options.push(t);
                                if (options.length >= 15) break;
                            }
                        }
                        inputs.push({
                            role, type, name,
                            label: (ariaLabel || labelText || '').slice(0, 80),
                            placeholder: (e.getAttribute('placeholder') || '').slice(0, 80),
                            has_popup: e.getAttribute('aria-haspopup') || '',
                            autocomplete: e.getAttribute('aria-autocomplete') || '',
                            options,
                        });
                        if (inputs.length >= 20) break;
                    }
                    const submits = [];
                    for (const b of modal.querySelectorAll('button[type="submit"], input[type="submit"]')) {
                        const t = (b.innerText || b.getAttribute('aria-label') || b.getAttribute('value') || '').trim().slice(0, 40);
                        if (t && submits.indexOf(t) < 0) submits.push(t);
                        if (submits.length >= 5) break;
                    }
                    const form = modal.querySelector('form[action]');
                    return {
                        inputs,
                        submit_labels: submits,
                        form_action: form ? form.getAttribute('action') : null,
                        form_method: form ? (form.getAttribute('method') || 'GET').toUpperCase() : null,
                    };
                }
                """
            )
            if entry and entry.get("inputs"):
                out.append({
                    "trigger_label": label,
                    **entry,
                })
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            await page.wait_for_timeout(200)
            if page.url != original_url:
                try:
                    await page.goto(original_url, wait_until="domcontentloaded", timeout=8000)
                except Exception:
                    break
        except Exception:
            continue
    return out


async def _enumerate_click_dropdowns(
    page, original_url: str
) -> list[dict]:
    """Click each unseen dropdown toggle, read newly visible menu options, revert.

    Complement to STATIC_DROPDOWN_EXTRACT_JS: targets toggles whose menu content
    is lazily inserted into DOM only after click. ARIA contract for a toggle
    with aria-haspopup=menu/listbox is that opening is view-only (no state
    change), so clicking is safe.
    """
    captured: list[dict] = []
    try:
        tog_locators = page.locator(
            '[aria-haspopup="menu"], [aria-haspopup="listbox"], [role="combobox"]'
        )
        total = await tog_locators.count()
    except Exception:
        return captured
    total = min(total, DROPDOWN_CAPTURE_LIMIT)
    for idx in range(total):
        try:
            tog = tog_locators.nth(idx)
            if not await tog.is_visible():
                continue
            label_raw = (await tog.inner_text() or
                         await tog.get_attribute("aria-label") or "").strip()
            label = label_raw.replace("\n", " ")[:80]
            if not label:
                continue
            try:
                await tog.click(timeout=2000)
            except Exception:
                continue
            try:
                await page.wait_for_timeout(200)
            except Exception:
                pass
            # Scrape any newly visible menuitem/option
            opts = await page.evaluate(r"""
                () => {
                    const out = [];
                    const nodes = document.querySelectorAll(
                        '[role="menu"]:not([aria-hidden="true"]) [role="menuitem"], '
                        + '[role="menu"]:not([aria-hidden="true"]) [role="menuitemcheckbox"], '
                        + '[role="menu"]:not([aria-hidden="true"]) [role="menuitemradio"], '
                        + '[role="listbox"]:not([aria-hidden="true"]) [role="option"]'
                    );
                    for (const n of nodes) {
                        if (n.offsetParent === null) continue;
                        const name = ((n.innerText || n.textContent || n.getAttribute('aria-label') || '') + '').trim().replace(/\s+/g, ' ');
                        if (!name || name.length > 120) continue;
                        const href = n.getAttribute('href') || null;
                        out.push({name, href});
                        if (out.length >= 30) break;
                    }
                    return out;
                }
            """)
            if opts:
                captured.append({"label": label, "options": opts})
            # Close menu via Escape to revert state
            try:
                await page.keyboard.press("Escape", timeout=1000)
            except Exception:
                pass
        except Exception:
            continue
        finally:
            if page.url != original_url:
                try:
                    await page.goto(original_url, wait_until="domcontentloaded", timeout=10000)
                except Exception:
                    break
    return captured


async def _capture_tab_click_urls(
    page, original_url: str, existing_hrefs: set[str]
) -> list[dict]:
    """Click each role=tab with href='#' or no href, record URL change as action.

    Returns list of captured action dicts matching ACTION_EXTRACT_JS shape.
    Errors or navigations away from the list page (different path) are discarded.
    """
    captured: list[dict] = []
    try:
        tab_locators = page.locator('[role="tab"]')
        count = await tab_locators.count()
    except Exception:
        return captured
    count = min(count, TAB_CAPTURE_LIMIT)
    for idx in range(count):
        try:
            el = tab_locators.nth(idx)
            if not await el.is_visible():
                continue
            href_attr = (await el.get_attribute("href")) or ""
            # Only click tabs whose static href is unresolvable (# / empty)
            if href_attr and href_attr != "#":
                continue
            label = ((await el.inner_text()) or "").strip().replace("\n", " ")
            if not label or len(label) > 120:
                continue
            try:
                await el.click(timeout=3000)
            except Exception:
                continue
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass
            new_url = page.url
            if not new_url or new_url == original_url:
                continue
            if new_url in existing_hrefs:
                continue
            existing_hrefs.add(new_url)
            captured.append({
                "label": label,
                "tag": "a",
                "href": new_url,
                "role": "tab",
                "type": None,
            })
        except Exception:
            continue
        finally:
            # Revert to original URL so subsequent tab clicks start from same state.
            try:
                if page.url != original_url:
                    await page.goto(original_url, wait_until="domcontentloaded", timeout=10000)
            except Exception:
                break  # if revert fails, abandon remaining tabs on this URL
    return captured


def _merge_dropdowns(static_list: list[dict], click_list: list[dict]) -> list[dict]:
    """Merge static + click-sourced dropdown captures, dedup by label.

    Each entry: {label, options: [{name, href?, value?}], param?}.
    Static source takes precedence if both exist (already has param for <select>).
    """
    merged: dict[str, dict] = {}
    for entry in static_list or []:
        lbl = (entry.get("label") or "").strip()
        if not lbl:
            continue
        merged[lbl] = entry
    for entry in click_list or []:
        lbl = (entry.get("label") or "").strip()
        if not lbl or lbl in merged:
            continue
        merged[lbl] = entry
    return list(merged.values())


def load_pool() -> list[dict]:
    pool = []
    for p in POOL_PATHS:
        if p.exists():
            pool.extend(json.loads(p.read_text(encoding="utf-8")))
    return pool


def pick_sample_urls(pool: list[dict]) -> dict[str, list[str]]:
    """Per class, collect up to SAMPLES_PER_CLASS URLs."""
    by_class: dict[str, list[str]] = defaultdict(list)
    for r in pool:
        cls = r.get("final_class")
        if not cls:
            continue
        url = r.get("final_url") or r.get("url")
        if not url:
            continue
        if len(by_class[cls]) < SAMPLES_PER_CLASS:
            # Dedup same-URL
            if url not in by_class[cls]:
                by_class[cls].append(url)
    return dict(by_class)


async def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pool = load_pool()
    print(f"Pool size: {len(pool)} records")
    class_samples = pick_sample_urls(pool)
    print(f"Classes: {len(class_samples)}")
    total_urls = sum(len(v) for v in class_samples.values())
    print(f"Total URLs to visit: {total_urls}")

    import os as _os_mod
    from site_adaptive_webagent.kg.site_plugin import load_site_plugin
    _plugin = load_site_plugin(_os_mod.getenv("SITE_NAME", "gitlab"))
    filter_category_params = getattr(_plugin, "filter_category_params", {}) or {}
    print(f"[stage_b_collect_actions] filter_category_params: {len(filter_category_params)} entries")

    # Classes eligible for deep (3-level) filter expansion: list-type classes
    # where a filtered-search input is likely to exist. `_detail`, `_new_form`,
    # etc. are skipped. Per-class expansion runs on the first sample URL only
    # (class is a leaf node — UI generalizes across instances).
    LIST_SUFFIXES = ("_list", "_board", "_feed")

    results: dict[str, dict] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx_kwargs = {}
        if STORAGE_STATE.exists():
            ctx_kwargs["storage_state"] = str(STORAGE_STATE)
        ctx = await browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()
        page.set_default_timeout(15000)

        i = 0
        for cls, urls in sorted(class_samples.items()):
            cls_actions: list[dict] = []
            cls_filter_categories: list[dict] = []
            cls_modal_structures: list[dict] = []
            # Deep 3-level expansion is allowed for list-type classes only,
            # and only on the first sample URL (class is a leaf — UI generalizes).
            deep_eligible = any(cls.endswith(sfx) for sfx in LIST_SUFFIXES)
            for url_idx, url in enumerate(urls):
                i += 1
                try:
                    resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(DELAY_MS)
                    if resp and resp.status == 200:
                        actions = await page.evaluate(ACTION_EXTRACT_JS)
                        # Tab click URL capture (static href=# tabs → query-param URL).
                        existing_hrefs = {
                            a.get("href") for a in actions if a.get("href")
                        }
                        extra = await _capture_tab_click_urls(
                            page, original_url=url, existing_hrefs=existing_hrefs,
                        )
                        actions.extend(extra)
                        try:
                            forms = await page.evaluate(FORM_EXTRACT_JS)
                        except Exception:
                            forms = []
                        # Shallow AXTree-based filter extraction — cheap,
                        # runs on every URL.
                        try:
                            filter_controls = await _extract_ax_filter_controls(
                                page, original_url=url,
                            )
                        except Exception:
                            filter_controls = []
                        # Deep 3-level filter expansion — only for list-type
                        # classes and only on the first sample URL.
                        if deep_eligible and url_idx == 0 and not cls_filter_categories:
                            try:
                                cls_filter_categories = await _extract_filter_categories(
                                    page, original_url=url,
                                    filter_category_params=filter_category_params,
                                )
                            except Exception:
                                cls_filter_categories = []
                        # Modal structural capture — any page can host dialog
                        # triggers (member list, settings, group, etc.). Only
                        # the first sample URL per class, to keep cost bounded.
                        if url_idx == 0 and not cls_modal_structures:
                            try:
                                cls_modal_structures = await _extract_modal_structures(
                                    page, original_url=url,
                                )
                            except Exception:
                                cls_modal_structures = []
                    else:
                        actions = []
                        forms = []
                        filter_controls = []
                except Exception as e:
                    actions = [{"error": str(e)[:100]}]
                    forms = []
                    filter_controls = []
                cls_actions.append({
                    "url": url,
                    "actions": actions,
                    "forms": forms,
                    "filter_controls": filter_controls,
                })
                if i % 50 == 0:
                    print(f"  [{i}/{total_urls}] visited, current class={cls}")
            results[cls] = {
                "sample_count": len(urls),
                "instances": cls_actions,
                "filter_categories": cls_filter_categories,
                "modal_structures": cls_modal_structures,
            }
        await browser.close()

    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {OUT}")
    # Summary
    total_actions = sum(
        sum(len(inst["actions"]) for inst in cls_data["instances"])
        for cls_data in results.values()
    )
    print(f"Total raw actions collected: {total_actions}")
    print(f"Classes processed: {len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
