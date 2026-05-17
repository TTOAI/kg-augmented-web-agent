"""runtime/browser.py 유닛 테스트."""
from __future__ import annotations

import unittest

from kg_augmented_webagent.runtime.browser import (
    LINK_SELECTORS,
    extract_ax_links,
    extract_texts,
    observe_page,
    try_click_target,
)

from .fixtures import FakePage, make_fake_page


class ExtractTextsTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_inner_text_when_present(self) -> None:
        page = make_fake_page(links=["Dashboard", "Issues", "Merge Requests"])
        texts = await extract_texts(page, LINK_SELECTORS)
        self.assertIn("Dashboard", texts)
        self.assertIn("Issues", texts)

    async def test_falls_back_to_aria_label_for_icon_links(self) -> None:
        """inner_text가 빈 링크는 aria-label로 대체돼야 한다 (예: GitLab 상단 nav 아이콘)."""
        page = FakePage(
            url="http://gitlab.example.com",
            title_text="GitLab",
            selector_texts={"a": ["", ""]},  # 두 링크 모두 텍스트 없음
            element_attributes={
                ("a", 0): {"aria-label": "Todos"},
                ("a", 1): {"aria-label": "Merge requests"},
            },
        )
        texts = await extract_texts(page, ("a",))
        self.assertIn("Todos", texts)
        self.assertIn("Merge requests", texts)

    async def test_falls_back_to_title_if_no_aria_label(self) -> None:
        page = FakePage(
            url="http://example.com",
            title_text="Page",
            selector_texts={"button": [""]},
            element_attributes={("button", 0): {"title": "Close dialog"}},
        )
        texts = await extract_texts(page, ("button",))
        self.assertIn("Close dialog", texts)

    async def test_skips_element_when_no_text_and_no_attrs(self) -> None:
        page = FakePage(
            url="http://example.com",
            title_text="Page",
            selector_texts={"a": [""]},
            element_attributes={},
        )
        texts = await extract_texts(page, ("a",))
        self.assertEqual(texts, [])

    async def test_deduplicates_texts(self) -> None:
        page = make_fake_page(links=["Home", "Home", "Dashboard"])
        texts = await extract_texts(page, LINK_SELECTORS)
        self.assertEqual(texts.count("Home"), 1)

    async def test_prefers_inner_text_over_aria_label(self) -> None:
        """inner_text가 있으면 aria-label을 무시한다."""
        page = FakePage(
            url="http://example.com",
            title_text="Page",
            selector_texts={"a": ["Real Text"]},
            element_attributes={("a", 0): {"aria-label": "Aria Label"}},
        )
        texts = await extract_texts(page, ("a",))
        self.assertIn("Real Text", texts)
        self.assertNotIn("Aria Label", texts)


class TryClickTargetTests(unittest.IsolatedAsyncioTestCase):
    async def test_clicks_by_inner_text(self) -> None:
        page = make_fake_page(links=["Dashboard", "Issues"])
        result = await try_click_target(page, ["dashboard"])
        self.assertTrue(result)

    async def test_clicks_icon_link_by_aria_label(self) -> None:
        """inner_text가 없는 icon-only 링크도 aria-label로 클릭할 수 있어야 한다."""
        page = FakePage(
            url="http://gitlab.example.com",
            title_text="GitLab",
            selector_texts={"a": [""]},  # icon-only 링크
            element_attributes={("a", 0): {"aria-label": "Todos"}},
            click_updates={("a", 0): {"url": "http://gitlab.example.com/dashboard/todos"}},
        )
        result = await try_click_target(page, ["todos"])
        self.assertTrue(result)
        self.assertEqual(page.url, "http://gitlab.example.com/dashboard/todos")

    async def test_returns_false_when_no_match(self) -> None:
        page = make_fake_page(links=["Home", "Issues"])
        result = await try_click_target(page, ["nonexistent"])
        self.assertFalse(result)

    async def test_clicks_by_title_attribute(self) -> None:
        page = FakePage(
            url="http://example.com",
            title_text="Page",
            selector_texts={"button": [""]},
            element_attributes={("button", 0): {"title": "Close dialog"}},
            click_updates={("button", 0): {"url": "http://example.com/closed"}},
        )
        result = await try_click_target(page, ["close"])
        self.assertTrue(result)


class ExtractAxLinksTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_name_and_pathname(self) -> None:
        """aria-label과 pathname을 함께 반환한다."""
        page = FakePage(
            url="http://gitlab.example.com/",
            title_text="GitLab",
            selector_texts={},
            evaluate_links=["To-Do List → /dashboard/todos", "Dashboard → /dashboard"],
        )
        links = await extract_ax_links(page)
        self.assertIn("To-Do List → /dashboard/todos", links)
        self.assertIn("Dashboard → /dashboard", links)

    async def test_falls_back_to_empty_when_evaluate_fails(self) -> None:
        """evaluate()가 실패하면 빈 리스트를 반환한다."""
        page = FakePage(url="http://example.com", title_text="Page", selector_texts={})
        links = await extract_ax_links(page)
        self.assertEqual(links, [])


class ObservePageTests(unittest.IsolatedAsyncioTestCase):
    async def test_observe_links_include_pathname(self) -> None:
        """observe_page()가 aria-label+pathname 형식의 링크를 반환한다."""
        page = FakePage(
            url="http://gitlab.example.com/dashboard",
            title_text="GitLab",
            selector_texts={},
            evaluate_links=["To-Do List → /dashboard/todos", "Dashboard → /dashboard"],
        )
        obs = await observe_page(page)
        self.assertIn("To-Do List → /dashboard/todos", obs.links)

    async def test_observe_falls_back_to_css_when_evaluate_fails(self) -> None:
        """evaluate()가 실패하면 CSS selector 폴백으로 링크를 수집한다."""
        page = make_fake_page(links=["Dashboard", "Issues"])
        obs = await observe_page(page)
        self.assertIn("Dashboard", obs.links)


if __name__ == "__main__":
    unittest.main()
