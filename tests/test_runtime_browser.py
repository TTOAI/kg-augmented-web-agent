"""runtime/browser.py 유닛 테스트."""
from __future__ import annotations

import unittest
from typing import Any

from site_adaptive_webagent.runtime.browser import extract_texts, observe_page
from site_adaptive_webagent.runtime.intent import LINK_SELECTORS, BUTTON_SELECTORS

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


class ObservePageTests(unittest.IsolatedAsyncioTestCase):
    async def test_observe_includes_aria_label_links(self) -> None:
        """observe_page()가 aria-label 링크를 links 필드에 포함한다."""
        page = FakePage(
            url="http://gitlab.example.com/dashboard",
            title_text="GitLab",
            selector_texts={
                "h1": [],
                "h2": [],
                "[role='heading']": [],
                "main": [],
                "article": [],
                "body": [],
                "a": [""],  # 아이콘 링크 (todos)
                "button": [],
                "[role='button']": [],
                "input[type='text']": [],
                "input[type='email']": [],
                "input[type='search']": [],
                "input[type='password']": [],
                "input[type='number']": [],
                "input:not([type])": [],
                "textarea": [],
                "select": [],
            },
            element_attributes={("a", 0): {"aria-label": "Todos"}},
        )
        obs = await observe_page(page)
        self.assertIn("Todos", obs.links)


if __name__ == "__main__":
    unittest.main()
