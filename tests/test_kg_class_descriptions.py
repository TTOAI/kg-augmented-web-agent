"""Tests for kg_solution.class_descriptions."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from site_adaptive_webagent.kg.runtime.class_descriptions import (
    ClassCatalog,
    load_class_catalog,
)


class ClassCatalogTests(unittest.TestCase):
    def _make_file(self, entries: dict) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump({"entries": entries}, tmp)
        tmp.close()
        return Path(tmp.name)

    def test_load_and_lookup(self):
        path = self._make_file({
            "project/issue_list": {
                "url_template": "/{namespace}/{project}/-/issues",
                "description": "Issue list.",
            },
            "project/main": {
                "url_template": "/{namespace}/{project}",
                "description": "Repo home.",
            },
        })
        catalog = load_class_catalog(path)
        self.assertEqual(len(catalog.class_names), 2)
        self.assertIn("project/issue_list", catalog)
        entry = catalog.get("project/issue_list")
        assert entry is not None
        self.assertEqual(entry.url_template, "/{namespace}/{project}/-/issues")

    def test_missing_class_returns_none(self):
        path = self._make_file({
            "a/b": {"url_template": None, "description": ""}
        })
        catalog = load_class_catalog(path)
        self.assertIsNone(catalog.get("nonexistent"))

    def test_format_for_prompt_ordered(self):
        path = self._make_file({
            "b/c": {"url_template": "/x", "description": "Class B."},
            "a/b": {"url_template": "/y", "description": "Class A."},
        })
        catalog = load_class_catalog(path)
        formatted = catalog.format_for_prompt()
        # deterministic alphabetical order
        a_idx = formatted.find("a/b")
        b_idx = formatted.find("b/c")
        self.assertLess(a_idx, b_idx)

    def test_format_omits_empty_fields(self):
        path = self._make_file({
            "a/b": {"url_template": None, "description": ""}
        })
        catalog = load_class_catalog(path)
        formatted = catalog.format_for_prompt()
        self.assertIn("a/b", formatted)
        self.assertNotIn("URL=", formatted)

    def test_real_class_descriptions_file_loads(self):
        real = (
            Path(__file__).resolve().parents[1]
            / "output" / "validation" / "kg_solution"
            / "class_descriptions.json"
        )
        if not real.exists():
            self.skipTest("class_descriptions.json not built")
        catalog = load_class_catalog(real)
        self.assertGreater(len(catalog.class_names), 100)
        self.assertIn("project/issue_list", catalog)


if __name__ == "__main__":
    unittest.main()
