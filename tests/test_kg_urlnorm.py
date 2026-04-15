"""kg.urlnorm 단위 테스트 — 정규화 8차원 + 라운드트립 + 예상 반박 시나리오."""
from __future__ import annotations

import unittest

from site_adaptive_webagent.kg import (
    IdentityParam,
    SiteConfig,
    StatePattern,
    emit_url,
    match_pattern,
    normalize_url,
)


def _gitlab_config() -> SiteConfig:
    """task 339·448 등 실측에서 관찰된 GitLab 정규화 규칙을 반영한 SiteConfig."""
    return SiteConfig(
        site="gitlab",
        base_url="http://localhost:8023",
        url_decode=True,
        trailing_slash_ignore=True,
        strip_fragment=True,
        path_case_sensitive=True,
        query_key_case_sensitive=True,
        query_value_case_sensitive=False,
        decorative_params=["page", "per_page", "sort_direction", "utm_*"],
        multi_value_suffix_pattern=r"\[\]$",
        multi_value_explicit=["approver_ids", "reviewer_ids"],
        identity_tokens={"me": "{{current_user.username}}"},
        path_aliases=[["/-/profile", "/profile"]],
        emit_include_default_values=True,
        emit_multi_value_sorted=True,
    )


def _issues_filtered_pattern() -> StatePattern:
    """task 339의 target state: 특정 project의 필터링된 issues 리스트."""
    return StatePattern(
        id="project_issues_filtered",
        url_template="/{project_path}/-/issues",
        path_params={"project_path": {"type": "path_segments"}},
        identity_query_params=[
            IdentityParam(
                name="state",
                type="enum",
                values=["opened", "closed", "all"],
                default="opened",
                required=False,
            ),
            IdentityParam(
                name="label_name[]",
                type="multi_string",
                default=[],
                required=False,
            ),
            IdentityParam(
                name="assignee_username",
                type="string",
                default=None,
                required=False,
            ),
        ],
        canonical_emit_order=["state", "label_name[]", "assignee_username"],
    )


# ---------------------------------------------------------------------------
# 1. 정규화 8차원
# ---------------------------------------------------------------------------

class Normalize8DimensionTests(unittest.TestCase):
    """02_open_questions.md §3-3의 URL 정규화 8차원 전수 검증."""

    def setUp(self) -> None:
        self.config = _gitlab_config()
        self.pattern = _issues_filtered_pattern()
        self.identity_names = {p.name for p in self.pattern.identity_query_params}

    def test_dim1_path_param_extraction(self) -> None:
        """dim 1: path_template의 {slot} 추출."""
        ok, bindings = match_pattern(
            "/a11yproject/a11yproject.com/-/issues?state=opened",
            self.pattern, self.config,
        )
        self.assertTrue(ok)
        self.assertEqual(bindings["project_path"], "a11yproject/a11yproject.com")

    def test_dim2_query_param_order_invariance(self) -> None:
        """dim 2: query param 순서가 달라도 같은 canonical로 귀결."""
        url_a = "/p/-/issues?state=opened&label_name[]=bug"
        url_b = "/p/-/issues?label_name[]=bug&state=opened"
        nA = normalize_url(url_a, self.config, identity_param_names=self.identity_names)
        nB = normalize_url(url_b, self.config, identity_param_names=self.identity_names)
        self.assertEqual(nA.query_pairs, nB.query_pairs)

    def test_dim3_url_encoding_normalized(self) -> None:
        """dim 3: %5B%5D → []. url_decode=True로 자동."""
        url_encoded = "/p/-/issues?label_name%5B%5D=bug&state=opened"
        url_plain = "/p/-/issues?label_name[]=bug&state=opened"
        nA = normalize_url(url_encoded, self.config, identity_param_names=self.identity_names)
        nB = normalize_url(url_plain, self.config, identity_param_names=self.identity_names)
        self.assertEqual(nA.query_pairs, nB.query_pairs)

    def test_dim4_default_value_fills_in_match(self) -> None:
        """dim 4: state 값 없으면 default='opened'로 bind."""
        ok, bindings = match_pattern(
            "/p/-/issues?label_name[]=bug",
            self.pattern, self.config,
        )
        self.assertTrue(ok)
        self.assertEqual(bindings["state"], "opened")
        self.assertEqual(bindings["label_name[]"], ["bug"])

    def test_dim5_decorative_params_removed(self) -> None:
        """dim 5: page, utm_* 같은 decorative param은 비교에서 제외."""
        url = "/p/-/issues?state=opened&page=2&utm_source=email"
        n = normalize_url(url, self.config, identity_param_names=self.identity_names)
        keys = {k for k, _ in n.query_pairs}
        self.assertNotIn("page", keys)
        self.assertNotIn("utm_source", keys)
        # 제거된 항목이 stripped에 기록되는지
        stripped_keys = {k for k, _ in n.stripped_decorative}
        self.assertIn("page", stripped_keys)
        self.assertIn("utm_source", stripped_keys)

    def test_dim6_multi_value_sorted(self) -> None:
        """dim 6: label_name[]=z 먼저, label_name[]=a 나중에 와도 정렬됨."""
        url_a = "/p/-/issues?label_name[]=z&label_name[]=a"
        ok, bindings = match_pattern(url_a, self.pattern, self.config)
        self.assertTrue(ok)
        self.assertEqual(bindings["label_name[]"], ["a", "z"])

    def test_dim7_identity_token_substitution(self) -> None:
        """dim 7: /me → runtime_context의 current_user.username으로 치환."""
        config = self.config
        # Pattern with identity token in path
        pattern = StatePattern(
            id="user_profile",
            url_template="/users/{user}",
            path_params={"user": {"type": "segment"}},
        )
        ok, bindings = match_pattern(
            "/users/me",
            pattern, config,
            runtime_context={"current_user": {"username": "byteblaze"}},
        )
        self.assertTrue(ok)
        self.assertEqual(bindings["user"], "byteblaze")

    def test_dim8_path_alias_canonicalized(self) -> None:
        """dim 8: /profile → /-/profile (canonical)."""
        pattern = StatePattern(
            id="user_profile_root",
            url_template="/-/profile",
        )
        ok, _ = match_pattern("/profile", pattern, self.config)
        self.assertTrue(ok)
        # reverse도 동작
        ok2, _ = match_pattern("/-/profile", pattern, self.config)
        self.assertTrue(ok2)


# ---------------------------------------------------------------------------
# 2. Task 339 end-to-end 라운드트립
# ---------------------------------------------------------------------------

class Task339RoundTripTests(unittest.TestCase):
    """실측 pilot task 339의 target URL이 match·emit에 안정적으로 처리되는지."""

    def setUp(self) -> None:
        self.config = _gitlab_config()
        self.pattern = _issues_filtered_pattern()

    def test_match_target_url(self) -> None:
        """실제 evaluator가 기대하는 URL이 pattern에 match + 올바른 bindings."""
        url = "/a11yproject/a11yproject.com/-/issues?state=opened&label_name[]=bug"
        ok, bindings = match_pattern(url, self.pattern, self.config)
        self.assertTrue(ok)
        self.assertEqual(bindings["project_path"], "a11yproject/a11yproject.com")
        self.assertEqual(bindings["state"], "opened")
        self.assertEqual(bindings["label_name[]"], ["bug"])

    def test_emit_from_bindings(self) -> None:
        """bindings → URL. canonical_emit_order 준수.

        GitLab은 label_name[]에 대해 '[]'를 그대로 표기 (URL-encoding 안 함).
        evaluator와 browser 양쪽 모두 decode로 통일되므로 [] 또는 %5B%5D 어느 쪽이든
        match 가능. 본 구현은 가독성 및 GitLab 관례에 맞춰 [] 그대로 emit한다.
        """
        url = emit_url(
            self.pattern,
            bindings={
                "project_path": "a11yproject/a11yproject.com",
                "state": "opened",
                "label_name[]": ["bug"],
            },
            site_config=self.config,
        )
        # state가 label_name[] 앞에 (canonical_emit_order)
        self.assertIn("state=opened", url)
        self.assertIn("label_name[]=bug", url)
        self.assertLess(url.index("state="), url.index("label_name"))

    def test_match_emit_roundtrip_semantic_equivalence(self) -> None:
        """match → emit 결과가 원 URL을 re-match했을 때 같은 bindings를 낸다."""
        original = "/a11yproject/a11yproject.com/-/issues?state=opened&label_name[]=bug"
        ok1, bindings1 = match_pattern(original, self.pattern, self.config)
        self.assertTrue(ok1)
        re_emitted = emit_url(self.pattern, bindings1, self.config)
        ok2, bindings2 = match_pattern(re_emitted, self.pattern, self.config)
        self.assertTrue(ok2)
        self.assertEqual(bindings1, bindings2)

    def test_param_order_in_input_does_not_affect_match(self) -> None:
        """input URL에서 param 순서가 뒤바뀌어도 match 결과 동일."""
        url_a = "/p/-/issues?state=opened&label_name[]=bug"
        url_b = "/p/-/issues?label_name[]=bug&state=opened"
        okA, bA = match_pattern(url_a, self.pattern, self.config)
        okB, bB = match_pattern(url_b, self.pattern, self.config)
        self.assertTrue(okA and okB)
        self.assertEqual(bA, bB)


# ---------------------------------------------------------------------------
# 3. 예외·edge case
# ---------------------------------------------------------------------------

class UrlnormEdgeCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = _gitlab_config()
        self.pattern = _issues_filtered_pattern()

    def test_no_match_when_path_differs(self) -> None:
        """/projects/-/issues가 아니라 /users면 match 실패."""
        ok, _ = match_pattern("/users/byteblaze", self.pattern, self.config)
        self.assertFalse(ok)

    def test_enum_violation_fails_match(self) -> None:
        """state=invalid는 enum에 없음 → match 실패."""
        url = "/p/-/issues?state=invalid&label_name[]=bug"
        ok, _ = match_pattern(url, self.pattern, self.config)
        self.assertFalse(ok)

    def test_missing_optional_binding_uses_default(self) -> None:
        """optional param 생략 시 default 값이 bindings에 들어간다."""
        url = "/p/-/issues"
        ok, bindings = match_pattern(url, self.pattern, self.config)
        self.assertTrue(ok)
        self.assertEqual(bindings["state"], "opened")
        self.assertEqual(bindings["label_name[]"], [])
        self.assertIsNone(bindings["assignee_username"])

    def test_trailing_slash_ignored(self) -> None:
        """/p/-/issues와 /p/-/issues/는 같게 처리."""
        u1 = "/p/-/issues"
        u2 = "/p/-/issues/"
        okA, bA = match_pattern(u1, self.pattern, self.config)
        okB, bB = match_pattern(u2, self.pattern, self.config)
        self.assertTrue(okA and okB)
        self.assertEqual(bA, bB)

    def test_emit_omits_none_and_empty_multi(self) -> None:
        """value=None 또는 empty list는 URL에 포함되지 않는다."""
        url = emit_url(
            self.pattern,
            bindings={
                "project_path": "p",
                "state": "opened",
                "label_name[]": [],
                "assignee_username": None,
            },
            site_config=self.config,
        )
        self.assertIn("state=opened", url)
        self.assertNotIn("label_name", url)
        self.assertNotIn("assignee_username", url)

    def test_decorative_param_does_not_affect_match(self) -> None:
        """URL에 page=2가 있어도 match 결과는 page 없는 URL과 같음."""
        u1 = "/p/-/issues?state=opened"
        u2 = "/p/-/issues?state=opened&page=2"
        ok1, b1 = match_pattern(u1, self.pattern, self.config)
        ok2, b2 = match_pattern(u2, self.pattern, self.config)
        self.assertTrue(ok1 and ok2)
        self.assertEqual(b1, b2)


if __name__ == "__main__":
    unittest.main()
