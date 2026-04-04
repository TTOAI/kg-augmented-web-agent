from __future__ import annotations

import unittest

from site_adaptive_webagent.agent.core import analyze_intent, run_agent


class FakeElementLocator:
    def __init__(self, page: "FakePage", selector: str, index: int) -> None:
        self.page = page
        self.selector = selector
        self.index = index

    async def inner_text(self) -> str:
        return self.page.selector_texts[self.selector][self.index]

    async def click(self) -> None:
        self.page.apply_click(self.selector, self.index)

    async def fill(self, value: str) -> None:
        self.page.last_filled = value

    async def press(self, key: str) -> None:
        self.page.last_pressed = key


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str) -> None:
        self.page = page
        self.selector = selector

    async def all_inner_texts(self) -> list[str]:
        return list(self.page.selector_texts.get(self.selector, []))

    async def count(self) -> int:
        return len(self.page.selector_texts.get(self.selector, []))

    def nth(self, index: int) -> FakeElementLocator:
        return FakeElementLocator(self.page, self.selector, index)


class FakePage:
    def __init__(
        self,
        *,
        url: str,
        title_text: str,
        selector_texts: dict[str, list[str]],
        click_updates: dict[tuple[str, int], dict[str, object]] | None = None,
    ) -> None:
        self.url = url
        self._title = title_text
        self.selector_texts = selector_texts
        self.click_updates = click_updates or {}
        self.last_filled: str | None = None
        self.last_pressed: str | None = None

    async def title(self) -> str:
        return self._title

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    async def goto(self, url: str) -> None:
        self.url = url

    def apply_click(self, selector: str, index: int) -> None:
        update = self.click_updates.get((selector, index), {})
        if "url" in update:
            self.url = str(update["url"])
        if "title" in update:
            self._title = str(update["title"])
        if "selector_texts" in update:
            self.selector_texts = dict(update["selector_texts"])


class AnalyzeIntentTests(unittest.TestCase):
    def test_classifies_retrieve_intent(self) -> None:
        plan = analyze_intent("Find the issue count on the project page")
        self.assertEqual(plan.task_type, "RETRIEVE")
        self.assertEqual(plan.action, "inspect_page")
        self.assertIn("issue", plan.target_terms)

    def test_classifies_navigate_intent_with_url(self) -> None:
        plan = analyze_intent("Open https://example.com/issues")
        self.assertEqual(plan.task_type, "NAVIGATE")
        self.assertEqual(plan.action, "goto_url")
        self.assertEqual(plan.explicit_url, "https://example.com/issues")


class RunAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_retrieves_matching_heading(self) -> None:
        page = FakePage(
            url="https://example.com/todos",
            title_text="Todos",
            selector_texts={
                "h1": ["Todo Count: 5"],
                "h2": [],
                "[role='heading']": [],
                "main": ["Todo Count: 5"],
                "article": [],
                "body": ["Todo Count: 5"],
                "a": [],
                "button": [],
                "[role='button']": [],
            },
        )

        result = await run_agent(
            intent="Find the todo count",
            sites=["gitlab"],
            start_urls=["https://example.com/todos"],
            task_id=1,
            context=None,
            pages=[page],
            task_output_dir=None,
        )

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.task_type, "RETRIEVE")
        self.assertEqual(result.retrieved_data, ["Todo Count: 5"])

    async def test_navigates_by_clicking_matching_link(self) -> None:
        page = FakePage(
            url="https://example.com/home",
            title_text="Home",
            selector_texts={
                "h1": ["Home"],
                "h2": [],
                "[role='heading']": [],
                "main": ["Welcome"],
                "article": [],
                "body": ["Welcome"],
                "a": ["Todos"],
                "button": [],
                "[role='button']": [],
            },
            click_updates={
                ("a", 0): {
                    "url": "https://example.com/todos",
                    "title": "Todos",
                    "selector_texts": {
                        "h1": ["My Todos"],
                        "h2": [],
                        "[role='heading']": [],
                        "main": ["My Todos"],
                        "article": [],
                        "body": ["My Todos"],
                        "a": [],
                        "button": [],
                        "[role='button']": [],
                    },
                }
            },
        )

        result = await run_agent(
            intent="Open my todos page",
            sites=["gitlab"],
            start_urls=["https://example.com/home"],
            task_id=2,
            context=None,
            pages=[page],
            task_output_dir=None,
        )

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.task_type, "NAVIGATE")

    async def test_returns_unknown_for_unsupported_intent(self) -> None:
        page = FakePage(
            url="https://example.com/home",
            title_text="Home",
            selector_texts={
                "h1": ["Home"],
                "h2": [],
                "[role='heading']": [],
                "main": ["Welcome"],
                "article": [],
                "body": ["Welcome"],
                "a": [],
                "button": [],
                "[role='button']": [],
            },
        )

        result = await run_agent(
            intent="Please reason deeply about the best next step",
            sites=["gitlab"],
            start_urls=["https://example.com/home"],
            task_id=3,
            context=None,
            pages=[page],
            task_output_dir=None,
        )

        self.assertEqual(result.status, "UNKNOWN_ERROR")


if __name__ == "__main__":
    unittest.main()
