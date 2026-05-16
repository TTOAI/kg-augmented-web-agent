"""Multi-site validation for path_finder.

CDIP positioning claim: "protocol은 site-agnostic, 구현은 GitLab 구체화".
이 테스트는 **runtime path_finder**가 GitLab 이외의 (합성) site taxonomy에
대해서도 올바르게 동작함을 확인한다. GitLab과 다른 naming convention, 다른
scope 체계, 다른 variant 명명을 사용하는 fake site를 만들어 cascade /
family extraction이 config 기반으로 동작하는지 검증.

이 테스트는 "CDIP가 개념적으로 site-agnostic이다"의 runtime 측 증거.
"""
from __future__ import annotations

import unittest

from site_adaptive_webagent.kg.runtime.path_finder import (
    CascadeConfig,
    extract_family,
    find_path,
)


# Fake site: 합성 e-commerce 스타일 taxonomy
# - scopes: shop, account, admin
# - family type suffixes: _catalog, _detail, _cart, _review (GitLab과 다름)
# - variant segments: mine, saved, popular (GitLab과 다름)
FAKE_CASCADE = CascadeConfig(
    scope_entries={
        "shop": "shop/home",
        "account": "account/profile",
        "admin": "admin/dashboard",
    },
    hub="shop/home",
    variant_segments=frozenset({"mine", "saved", "popular"}),
    family_type_suffixes=(
        "_catalog",
        "_detail",
        "_cart",
        "_review",
        "_form",
    ),
)


def _adj(*edges: tuple[str, str, str]) -> dict:
    """build adjacency from (src, tgt, trust) triples."""
    out: dict = {}
    for src, tgt, trust in edges:
        out.setdefault(src, []).append(
            {"target": tgt, "actions": [f"to_{tgt}"], "trust": trust}
        )
    return out


class FakeSiteFamilyExtractionTests(unittest.TestCase):
    """extract_family가 fake site의 variant/suffix를 인식."""

    def test_fake_site_catalog_family(self):
        self.assertEqual(
            extract_family("shop/product_catalog", config=FAKE_CASCADE),
            "shop/product",
        )

    def test_fake_site_detail_family(self):
        self.assertEqual(
            extract_family("shop/product_detail", config=FAKE_CASCADE),
            "shop/product",
        )

    def test_fake_site_cart_family(self):
        self.assertEqual(
            extract_family("shop/order_cart", config=FAKE_CASCADE),
            "shop/order",
        )

    def test_fake_site_variant_strip(self):
        self.assertEqual(
            extract_family("shop/wishlist_catalog/mine", config=FAKE_CASCADE),
            "shop/wishlist",
        )

    def test_fake_site_unknown_suffix_passthrough(self):
        # GitLab-style suffix (_list)는 fake site config에 없음 → 그대로 유지
        self.assertEqual(
            extract_family("shop/something_list", config=FAKE_CASCADE),
            "shop/something_list",
        )


class FakeSiteCascadeTests(unittest.TestCase):
    """find_path의 cascade stages가 fake site scope_entries / hub를 따라감."""

    def test_exact_on_fake_site(self):
        adj = _adj(
            ("shop/home", "shop/product_catalog", "high"),
            ("shop/product_catalog", "shop/product_detail", "high"),
        )
        result = find_path(
            adj,
            "shop/home",
            "shop/product_detail",
            all_classes={"shop/home", "shop/product_catalog", "shop/product_detail"},
            config=FAKE_CASCADE,
        )
        self.assertEqual(result.strategy, "exact")
        self.assertEqual(result.hops, 2)

    def test_family_sibling_on_fake_site(self):
        # target shop/product_detail은 도달 불가; sibling shop/product_catalog는 도달 가능
        adj = _adj(("A", "shop/product_catalog", "high"))
        result = find_path(
            adj,
            "A",
            "shop/product_detail",
            all_classes={"A", "shop/product_catalog", "shop/product_detail"},
            config=FAKE_CASCADE,
        )
        self.assertEqual(result.strategy, "family_sibling")
        self.assertEqual(result.actual_target, "shop/product_catalog")

    def test_scope_entry_on_fake_site(self):
        # target은 shop scope. scope_entry=shop/home 도달 가능.
        adj = _adj(("A", "shop/home", "high"))
        result = find_path(
            adj,
            "A",
            "shop/rare_page",
            all_classes={"A", "shop/home", "shop/rare_page"},
            config=FAKE_CASCADE,
        )
        self.assertEqual(result.strategy, "scope_entry")
        self.assertEqual(result.actual_target, "shop/home")

    def test_hub_fallback_on_fake_site(self):
        # scope entry (admin/dashboard) 미존재/미도달; hub=shop/home만 reachable.
        adj = _adj(("A", "shop/home", "high"))
        result = find_path(
            adj,
            "A",
            "admin/rare",
            all_classes={"A", "shop/home", "admin/rare"},
            config=CascadeConfig(
                scope_entries={"admin": "admin/unreachable"},
                hub="shop/home",
                variant_segments=FAKE_CASCADE.variant_segments,
                family_type_suffixes=FAKE_CASCADE.family_type_suffixes,
            ),
        )
        self.assertEqual(result.strategy, "hub_fallback")
        self.assertEqual(result.actual_target, "shop/home")

    def test_stay_and_explore_on_fake_site(self):
        adj = _adj()
        result = find_path(
            adj,
            "A",
            "shop/impossible",
            all_classes={"A", "shop/home", "shop/impossible"},
            config=FAKE_CASCADE,
        )
        self.assertEqual(result.strategy, "stay_and_explore")


class NoConfigFallbackTests(unittest.TestCase):
    """Config 없이 호출하면 module-level GitLab-flavored fallback을 사용해
    기존 GitLab 동작 유지 (하위 호환 + standalone import)."""

    def test_extract_family_without_config_uses_module_default(self):
        # GitLab convention: project/issue_list → project/issue
        self.assertEqual(extract_family("project/issue_list"), "project/issue")

    def test_extract_family_with_empty_config_falls_back_to_module(self):
        empty_config = CascadeConfig(
            scope_entries={}, hub="",
            variant_segments=frozenset(), family_type_suffixes=(),
        )
        # Empty config → module-level VARIANT_SEGMENTS + FAMILY_TYPE_SUFFIXES 사용
        self.assertEqual(
            extract_family("dashboard/project_list/yours", config=empty_config),
            "dashboard/project",
        )


if __name__ == "__main__":
    unittest.main()
