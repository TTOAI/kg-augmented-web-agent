"""Site-pluggable URL template derivation.

URL template 도출에서 site-specific 부분을 generic 알고리즘 밖 plugin으로
분리한다. Cross-site KG 구축 시 generic skeleton은 그대로 두고 사이트별
plugin만 추가하면 되도록 하는 것이 목적이다.

Protocol 레벨 skeleton:
  - URL path를 segment list로 쪼갠다 (site-agnostic)
  - segment 리스트에서 prefix 매칭 + per-segment classification으로 template 생성
  - site-specific 부분은 `SitePlugin.derive_path_template(segments, entities, action_keywords)` 호출

Plugin 책임:
  - URL 스키마별 prefix 인식 (`/{ns}/{proj}` vs `/f/<forum>` vs ...)
  - segment 종류 판정 (numeric ID, SHA, 사용자명, 브랜치 경로 등)
  - path_params dict 반환 (template var → metadata)

Registry는 `load_site_plugin(site_name)`. SITE_NAME env 또는 명시 호출로 로드.
Plugin 미존재 시 `DefaultSitePlugin` (numeric/SHA만 일반화, 나머지 segment는
literal 유지) fallback — site-agnostic baseline이지만 template 정밀도는 낮음.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol, runtime_checkable

import yaml

from .site_extras import SiteEntities

_CONFIG_ROOT = Path("config/sites")


def _load_class_taxonomy(
    site: str,
) -> tuple[dict[str, str], str, dict[tuple[str, str], list[str]], dict[str, str]]:
    """Load class_taxonomy.yaml for a site.

    Returns (scope_taxonomy, entity_noun, extra_triggers, filter_category_params).
    Missing file → empty taxonomy, "container" noun, empty extras, empty params.

    `extra_triggers` YAML uses `<scope>_<suffix>` keys; this function splits
    each into `(scope, suffix)` tuples.

    `filter_category_params` maps a site's filter-category label (e.g. "Label",
    "Assignee") to its URL query parameter (e.g. "label_name[]",
    "assignee_username"). Consumed by the recursive filter-control extractor
    to annotate captured categories with the correct URL param so the agent
    hint exposes a clean `goto(?param=value)` recipe.
    """
    path = _CONFIG_ROOT / site / "class_taxonomy.yaml"
    if not path.exists():
        return {}, "container", {}, {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}, "container", {}, {}
    scope_taxonomy = dict(data.get("scope_taxonomy") or {})
    entity_noun = str(data.get("entity_noun") or "container")
    raw_extras = data.get("extra_triggers") or {}
    extra_triggers: dict[tuple[str, str], list[str]] = {}
    for key, phrases in raw_extras.items():
        if "_" not in key:
            continue
        scope_kind, suffix_kind = key.split("_", 1)
        extra_triggers[(scope_kind, suffix_kind)] = list(phrases or [])
    filter_category_params = {
        str(k): str(v) for k, v in (data.get("filter_category_params") or {}).items()
    }
    return scope_taxonomy, entity_noun, extra_triggers, filter_category_params


@runtime_checkable
class SitePlugin(Protocol):
    """Per-site URL template derivation contract.

    Implementations: GitLabSitePlugin, RedditSitePlugin, ...
    """

    site: str

    def derive_path_template(
        self,
        segments: list[str],
        *,
        entities: SiteEntities,
    ) -> tuple[str, dict[str, dict]]:
        """Given URL path segments, return (template_path, path_params).

        Args:
          segments: path without leading/trailing slash, split on '/'.
                    예: ["a", "b", "{ns}", "{proj}"] 형태의 토큰 리스트
          entities: SiteEntities (namespaces, usernames, action_keywords, sample_values).

        Returns:
          template_path: "/a/b/{c}" 형태 (leading slash 포함).
          path_params: {"c": {"type": "segment"|"path_segments"}, ...}
        """
        ...

    # Scope taxonomy for class_descriptions structured fields.
    # Maps the class-name prefix (the part before '/') to a scope kind that
    # task_inferrer uses for disambiguation. Values loaded per plugin from
    # `config/sites/<site>/class_taxonomy.yaml`.
    scope_taxonomy: dict[str, str]

    # Binding noun used when phrasing entity-scoped triggers/role
    # ("X in a named <entity_noun>"). Loaded from the same YAML.
    entity_noun: str

    # Extra trigger phrases appended beyond the universal base, keyed by
    # (scope_kind, suffix_kind) where suffix_kind ∈ {"list","detail","form",""}.
    # Each phrase may include "{resource}" as a placeholder substituted at
    # build time with the resource noun derived from the class name. Loaded
    # from the same YAML.
    extra_triggers: dict[tuple[str, str], list[str]]

    # Filter-category label → URL query parameter mapping, used by the
    # recursive filter-control extractor to annotate captured categories
    # (e.g. "Label" → "label_name[]") so agent hints expose a clean
    # `goto(?param=value)` recipe.
    filter_category_params: dict[str, str]


_NUMERIC_RE = re.compile(r"^\d+$")
_SHA_RE = re.compile(r"^[0-9a-f]{8,40}$")
_LONG_HEX_RE = re.compile(r"^[0-9a-f]{16,40}$")


def classify_common_segment(
    seg: str, prev: str | None, action_keywords: frozenset[str]
) -> tuple[str | None, dict | None]:
    """Common segment classifications that apply site-agnostically.

    Returns (template_token, param_metadata) or (None, None) if not classified.
    Plugins call this first for generic segments (IDs, SHAs) before applying
    site-specific rules.
    """
    if seg in action_keywords:
        return seg, None  # literal action keyword
    if _NUMERIC_RE.match(seg):
        return "{id}", {"type": "segment"}
    if _SHA_RE.match(seg):
        return "{sha}", {"type": "segment"}
    # Uploads-style: SHA-like previous segment + filename here
    if prev and _LONG_HEX_RE.match(prev):
        return "{file}", {"type": "segment"}
    return None, None


class GitLabSitePlugin:
    """GitLab URL scheme plugin.

    Prefix patterns:
      - /-/ide/project/{namespace}/{project}/...  (Web IDE)
      - /users/{username}/...
      - /{namespace}/{project}/...  (main project URL)
      - /{username}  (single-segment user profile)

    Per-segment rules (GitLab-specific):
      - After tree/blob/raw/commits/blame/find_file → {branch_path} (rest of path)
      - After graphs/network → {branch}
      - After releases (with /-/ prefix) → {tag}
      - After tags (with /-/ prefix) → {tag_name}
      - After projects/topics/ → {topic_name}
      - After settings/integrations/ → {service}
      - After import/ → {service}
    """

    site = "gitlab"

    def __init__(self) -> None:
        # Class taxonomy lives in config/sites/gitlab/class_taxonomy.yaml —
        # keeps site-specific vocabulary out of plugin code.
        self.scope_taxonomy, self.entity_noun, self.extra_triggers, self.filter_category_params = (
            _load_class_taxonomy(self.site)
        )

    def derive_path_template(
        self,
        segments: list[str],
        *,
        entities: SiteEntities,
    ) -> tuple[str, dict[str, dict]]:
        if not segments or segments == [""]:
            return "/", {}

        namespaces = entities.namespaces
        usernames = entities.usernames
        action_keywords = entities.action_keywords

        template_segs: list[str] = []
        params: dict[str, dict] = {}
        i = 0

        # /-/ide/project/{ns}/{proj}/...
        if (
            len(segments) >= 5
            and segments[0] == "-"
            and segments[1] == "ide"
            and segments[2] == "project"
        ):
            template_segs.extend(["-", "ide", "project", "{namespace}", "{project}"])
            params["namespace"] = {"type": "segment"}
            params["project"] = {"type": "segment"}
            i = 5
        # /users/{username}/...
        elif len(segments) >= 2 and segments[0] == "users" and segments[1] in usernames:
            template_segs.extend(["users", "{username}"])
            params["username"] = {"type": "segment"}
            i = 2
        # /{namespace}/{project}/...
        elif len(segments) >= 2 and segments[0] in namespaces:
            template_segs.extend(["{namespace}", "{project}"])
            params["namespace"] = {"type": "segment"}
            params["project"] = {"type": "segment"}
            i = 2
        # /{username} (single-segment user profile)
        elif len(segments) == 1 and segments[0] in usernames:
            template_segs.append("{username}")
            params["username"] = {"type": "segment"}
            return "/" + "/".join(template_segs), params

        while i < len(segments):
            seg = segments[i]
            prev = segments[i - 1] if i > 0 else None
            # Common first: action keywords, IDs, SHAs, uploaded files after SHA
            token, meta = classify_common_segment(seg, prev, action_keywords)
            if token is not None and token == seg:
                template_segs.append(token)  # literal (action keyword)
            elif token in ("{id}", "{sha}", "{file}"):
                template_segs.append(token)
                if meta is not None:
                    # param name derived from token without braces
                    pname = token.strip("{}")
                    params[pname] = meta
            # GitLab-specific: branch path / branch / tags / releases / topics / services
            elif prev in ("tree", "blob", "raw", "commits", "blame", "find_file"):
                template_segs.append("{branch_path}")
                params["branch_path"] = {"type": "path_segments"}
                break
            elif prev in ("graphs", "network"):
                template_segs.append("{branch}")
                params["branch"] = {"type": "segment"}
            elif (
                i >= 2 and prev == "releases" and segments[i - 2] == "-"
                and seg not in action_keywords
            ):
                template_segs.append("{tag}")
                params["tag"] = {"type": "segment"}
            elif i >= 2 and prev == "tags" and segments[i - 2] == "-":
                template_segs.append("{tag_name}")
                params["tag_name"] = {"type": "segment"}
            elif i >= 2 and prev == "topics" and segments[i - 2] == "projects":
                template_segs.append("{topic_name}")
                params["topic_name"] = {"type": "segment"}
            elif i >= 2 and prev == "integrations" and segments[i - 2] == "settings":
                template_segs.append("{service}")
                params["service"] = {"type": "segment"}
            elif i >= 1 and prev == "import" and seg != "new":
                template_segs.append("{service}")
                params["service"] = {"type": "segment"}
            else:
                template_segs.append(seg)
            i += 1
        return "/" + "/".join(template_segs), params


class RedditSitePlugin:
    """Postmill URL scheme plugin.

    URL patterns:
      - /                                      (home)
      - /forums                                (forum list)
      - /f/{forum}                             (forum page)
      - /f/{forum}/submit                      (new post)
      - /f/{forum}/{post_id}                   (post, numeric id)
      - /f/{forum}/{post_id}/{slug}            (post with slug)
      - /f/{forum}/{post_id}/comment/{cid}     (comment)
      - /user/{username}                       (profile)
      - /user/{username}/comments              (user's comments)
      - /user/{username}/submissions           (user's posts)
      - /search
      - /submit                                (new submission)
      - /wiki/{path}                           (wiki)
      - /messages/{thread_id}                  (DM)
      - /login, /registration

    Prefix patterns:
      - /f/{forum}/...
      - /user/{username}/...
      - /wiki/... → /wiki/{page_path} (rest as path_segments)
    """

    site = "reddit"

    def __init__(self) -> None:
        self.scope_taxonomy, self.entity_noun, self.extra_triggers, self.filter_category_params = (
            _load_class_taxonomy(self.site)
        )

    def derive_path_template(
        self,
        segments: list[str],
        *,
        entities: SiteEntities,
    ) -> tuple[str, dict[str, dict]]:
        if not segments or segments == [""]:
            return "/", {}

        action_keywords = entities.action_keywords

        template_segs: list[str] = []
        params: dict[str, dict] = {}
        i = 0

        # /f/{forum}/...
        if len(segments) >= 2 and segments[0] == "f":
            template_segs.extend(["f", "{forum}"])
            params["forum"] = {"type": "segment"}
            i = 2
        # /user/{username}/...
        elif len(segments) >= 2 and segments[0] == "user":
            template_segs.extend(["user", "{username}"])
            params["username"] = {"type": "segment"}
            i = 2
        # /wiki/{page_path}  (wiki path may have multiple segments)
        elif len(segments) >= 2 and segments[0] == "wiki":
            template_segs.append("wiki")
            template_segs.append("{page_path}")
            params["page_path"] = {"type": "path_segments"}
            return "/" + "/".join(template_segs), params
        # /messages/{thread_id}
        elif len(segments) >= 2 and segments[0] == "messages":
            template_segs.append("messages")
            template_segs.append("{id}")
            params["id"] = {"type": "segment"}
            i = 2

        while i < len(segments):
            seg = segments[i]
            prev = segments[i - 1] if i > 0 else None
            token, meta = classify_common_segment(seg, prev, action_keywords)
            if token is not None and token == seg:
                template_segs.append(token)
            elif token in ("{id}", "{sha}", "{file}"):
                template_segs.append(token)
                if meta is not None:
                    pname = token.strip("{}")
                    params[pname] = meta
            # Reddit-specific: after post_id (numeric already generalized above)
            #   - comment/{id} pattern
            #   - {slug} after post_id (any non-action segment)
            elif prev == "comment":
                template_segs.append("{id}")
                params["id"] = {"type": "segment"}
            # Slug after numeric post_id → {slug} (slug varies and rarely
            # matters for KG classification, so generalize to a slot)
            elif prev and _NUMERIC_RE.match(prev) and seg not in action_keywords and seg != "comment":
                template_segs.append("{slug}")
                params["slug"] = {"type": "segment"}
            else:
                template_segs.append(seg)
            i += 1
        return "/" + "/".join(template_segs), params


class DefaultSitePlugin:
    """Fallback plugin when site-specific plugin unavailable.

    Only generalizes universal patterns (numeric IDs, SHAs). Other segments
    stay as literals. Template precision is low but site-agnostic — useful for
    quick exploration or sites without a dedicated plugin.
    """

    site = "default"

    def __init__(self) -> None:
        # Default plugin has no site-specific YAML; always empty taxonomy.
        self.scope_taxonomy: dict[str, str] = {}
        self.entity_noun: str = "container"
        self.extra_triggers: dict[tuple[str, str], list[str]] = {}

    def derive_path_template(
        self,
        segments: list[str],
        *,
        entities: SiteEntities,
    ) -> tuple[str, dict[str, dict]]:
        if not segments or segments == [""]:
            return "/", {}

        action_keywords = entities.action_keywords
        template_segs: list[str] = []
        params: dict[str, dict] = {}

        for i, seg in enumerate(segments):
            prev = segments[i - 1] if i > 0 else None
            token, meta = classify_common_segment(seg, prev, action_keywords)
            if token is not None and token == seg:
                template_segs.append(token)
            elif token in ("{id}", "{sha}", "{file}"):
                template_segs.append(token)
                if meta is not None:
                    pname = token.strip("{}")
                    params[pname] = meta
            else:
                template_segs.append(seg)
        return "/" + "/".join(template_segs), params


_REGISTRY: dict[str, SitePlugin] = {
    "gitlab": GitLabSitePlugin(),
    "reddit": RedditSitePlugin(),
    "default": DefaultSitePlugin(),
}


def load_site_plugin(site: str) -> SitePlugin:
    """Return the SitePlugin for `site`, or DefaultSitePlugin if unknown.

    Case-insensitive matching on site name.
    """
    key = site.lower().strip()
    if key in _REGISTRY:
        return _REGISTRY[key]
    return _REGISTRY["default"]
