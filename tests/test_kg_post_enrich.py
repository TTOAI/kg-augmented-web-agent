"""kg.seed.post_enrich 단위 테스트 — auto-enrichment 결함 보강 검증."""
from __future__ import annotations

import unittest

from site_adaptive_webagent.kg import (
    IdentityParam,
    InfoType,
    RealizesEdge,
    SiteKG,
    StatePattern,
)
from site_adaptive_webagent.kg.seed.post_enrich import (
    assign_infotype_category,
    auto_fill_binding_map,
    auto_fill_path_params,
    auto_fill_query_params,
    enrich,
)


class AutoFillPathParamsTests(unittest.TestCase):
    def test_path_segments_for_path_suffix_slots(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp1"] = StatePattern(
            id="sp1", url_template="/{project_path}/-/issues",
        )
        auto_fill_path_params(kg)
        self.assertEqual(
            kg.state_patterns["sp1"].path_params["project_path"]["type"],
            "path_segments",
        )

    def test_segment_for_generic_slot(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp1"] = StatePattern(
            id="sp1", url_template="/help/{doc_path}",
        )
        auto_fill_path_params(kg)
        self.assertEqual(
            kg.state_patterns["sp1"].path_params["doc_path"]["type"], "path_segments",
        )

    def test_generic_slot_segment(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp1"] = StatePattern(
            id="sp1", url_template="/{namespace}",
        )
        auto_fill_path_params(kg)
        self.assertEqual(kg.state_patterns["sp1"].path_params["namespace"]["type"], "segment")

    def test_existing_type_preserved(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp1"] = StatePattern(
            id="sp1", url_template="/{x}",
            path_params={"x": {"type": "int"}},
        )
        auto_fill_path_params(kg)
        self.assertEqual(kg.state_patterns["sp1"].path_params["x"]["type"], "int")

    def test_no_slots_no_change(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp1"] = StatePattern(id="sp1", url_template="/dashboard")
        count = auto_fill_path_params(kg)
        self.assertEqual(count, 0)


class AutoFillQueryParamsTests(unittest.TestCase):
    def test_optional_bindings_added_as_query(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp"] = StatePattern(id="sp", url_template="/search")
        it = InfoType(
            name="search",
            optional_bindings=["scope", "search_query"],
            realizes=[RealizesEdge(infotype="search", state_pattern_id="sp")],
        )
        kg.infotypes["search"] = it
        auto_fill_query_params(kg)
        names = {p.name for p in kg.state_patterns["sp"].identity_query_params}
        self.assertEqual(names, {"scope", "search_query"})

    def test_enum_hint_detected(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp"] = StatePattern(id="sp", url_template="/x")
        it = InfoType(
            name="x", optional_bindings=["state", "scope"],
            realizes=[RealizesEdge(infotype="x", state_pattern_id="sp")],
        )
        kg.infotypes["x"] = it
        auto_fill_query_params(kg)
        types = {p.name: p.type for p in kg.state_patterns["sp"].identity_query_params}
        self.assertEqual(types["state"], "enum")
        self.assertEqual(types["scope"], "enum")

    def test_multi_suffix_detected(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp"] = StatePattern(id="sp", url_template="/x")
        it = InfoType(
            name="x", optional_bindings=["label_name[]"],
            realizes=[RealizesEdge(infotype="x", state_pattern_id="sp")],
        )
        kg.infotypes["x"] = it
        auto_fill_query_params(kg)
        p = kg.state_patterns["sp"].identity_query_params[0]
        self.assertEqual(p.type, "multi_string")

    def test_id_suffix_int(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp"] = StatePattern(id="sp", url_template="/x")
        it = InfoType(
            name="x", optional_bindings=["project_id"],
            realizes=[RealizesEdge(infotype="x", state_pattern_id="sp")],
        )
        kg.infotypes["x"] = it
        auto_fill_query_params(kg)
        p = kg.state_patterns["sp"].identity_query_params[0]
        self.assertEqual(p.type, "int")

    def test_existing_query_param_not_duplicated(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp"] = StatePattern(
            id="sp", url_template="/x",
            identity_query_params=[IdentityParam(name="state", type="enum", values=["opened", "closed"])],
        )
        it = InfoType(
            name="x", optional_bindings=["state"],
            realizes=[RealizesEdge(infotype="x", state_pattern_id="sp")],
        )
        kg.infotypes["x"] = it
        auto_fill_query_params(kg)
        params = kg.state_patterns["sp"].identity_query_params
        self.assertEqual(len(params), 1)  # 추가되지 않음
        self.assertEqual(params[0].values, ["opened", "closed"])  # 기존 values 유지

    def test_path_slot_not_added_as_query(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp"] = StatePattern(
            id="sp", url_template="/{project_path}",
            path_params={"project_path": {"type": "path_segments"}},
        )
        it = InfoType(
            name="x", optional_bindings=["project_path"],
            realizes=[RealizesEdge(infotype="x", state_pattern_id="sp")],
        )
        kg.infotypes["x"] = it
        auto_fill_query_params(kg)
        # path slot에 이미 있으면 query param으로 추가 안 됨
        names = {p.name for p in kg.state_patterns["sp"].identity_query_params}
        self.assertEqual(names, set())


class AutoFillBindingMapTests(unittest.TestCase):
    def test_exact_name_match(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp"] = StatePattern(
            id="sp", url_template="/{project_path}",
            path_params={"project_path": {"type": "path_segments"}},
        )
        it = InfoType(
            name="x", required_bindings=["project_path"],
            realizes=[RealizesEdge(infotype="x", state_pattern_id="sp")],
        )
        kg.infotypes["x"] = it
        auto_fill_binding_map(kg)
        self.assertEqual(it.realizes[0].binding_map, {"project_path": "project_path"})

    def test_bracket_suffix_variant(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp"] = StatePattern(
            id="sp", url_template="/x",
            identity_query_params=[IdentityParam(name="label_name[]", type="multi_string")],
        )
        it = InfoType(
            name="x", optional_bindings=["label_name"],
            realizes=[RealizesEdge(infotype="x", state_pattern_id="sp")],
        )
        kg.infotypes["x"] = it
        auto_fill_binding_map(kg)
        self.assertEqual(it.realizes[0].binding_map, {"label_name": "label_name[]"})

    def test_existing_map_preserved(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp"] = StatePattern(
            id="sp", url_template="/{project_path}",
            path_params={"project_path": {"type": "path_segments"}},
        )
        it = InfoType(
            name="x", required_bindings=["project_path"],
            realizes=[RealizesEdge(
                infotype="x", state_pattern_id="sp",
                binding_map={"custom": "value"},
            )],
        )
        kg.infotypes["x"] = it
        auto_fill_binding_map(kg)
        self.assertEqual(it.realizes[0].binding_map, {"custom": "value"})


class AssignCategoryTests(unittest.TestCase):
    def test_cluster_prefix_becomes_category(self) -> None:
        kg = SiteKG(site="x")
        for name in ["project_home", "project_issue_list", "repository_tree", "repository_graphs"]:
            kg.infotypes[name] = InfoType(name=name)
        assign_infotype_category(kg)
        self.assertEqual(kg.infotypes["project_home"].category, "project")
        self.assertEqual(kg.infotypes["repository_tree"].category, "repository")

    def test_singleton_becomes_misc(self) -> None:
        kg = SiteKG(site="x")
        kg.infotypes["wiki_home"] = InfoType(name="wiki_home")
        kg.infotypes["project_home"] = InfoType(name="project_home")
        kg.infotypes["project_issue_list"] = InfoType(name="project_issue_list")
        assign_infotype_category(kg)
        self.assertEqual(kg.infotypes["wiki_home"].category, "misc")
        self.assertEqual(kg.infotypes["project_home"].category, "project")


class EnrichIntegrationTests(unittest.TestCase):
    def test_enrich_applies_all(self) -> None:
        kg = SiteKG(site="x")
        kg.state_patterns["sp"] = StatePattern(
            id="sp", url_template="/{project_path}/-/issues",
        )
        it = InfoType(
            name="project_issue_list",
            required_bindings=["project_path"],
            optional_bindings=["state"],
            realizes=[RealizesEdge(infotype="project_issue_list", state_pattern_id="sp")],
        )
        kg.infotypes["project_issue_list"] = it
        kg.infotypes["project_home"] = InfoType(name="project_home")
        kg.realizes_edges.extend(it.realizes)
        summary = enrich(kg)
        # path_params 채워짐
        self.assertEqual(
            kg.state_patterns["sp"].path_params["project_path"]["type"],
            "path_segments",
        )
        # query param 추가
        names = {p.name for p in kg.state_patterns["sp"].identity_query_params}
        self.assertIn("state", names)
        # binding_map 채워짐
        self.assertIn("project_path", it.realizes[0].binding_map)
        self.assertIn("state", it.realizes[0].binding_map)
        # category
        self.assertEqual(it.category, "project")
        # summary counts
        self.assertGreater(summary["D2_path_params"], 0)
        self.assertGreater(summary["D3_query_params"], 0)
        self.assertGreater(summary["D1_binding_map"], 0)
        self.assertGreater(summary["D6_category"], 0)


class BackfillFromFormActionsTests(unittest.TestCase):
    def test_form_edge_from_state_gets_query_params(self) -> None:
        from site_adaptive_webagent.kg.types import Action as _Action, LeadsToEdge as _LTE
        from site_adaptive_webagent.kg.seed.post_enrich import (
            backfill_query_params_from_form_actions,
        )
        kg = SiteKG(site="x")
        kg.state_patterns["sp_lit"] = StatePattern(
            id="sp_lit", url_template="/byteblaze/foo/-/project_members",
        )
        kg.state_patterns["sp_sem"] = StatePattern(
            id="sp_sem", url_template="/{project_path}/-/project_members",
        )
        action_name = "crawl:form:byteblaze_foo_project_members:search"
        kg.actions[action_name] = _Action(name=action_name)
        # self-loop edge at literal crawl SP
        kg.leads_to_edges.append(_LTE(
            from_state_pattern_id="sp_lit",
            action_name=action_name,
            to_state_pattern_id="sp_lit",
        ))
        backfill_query_params_from_form_actions(kg)
        # literal SP에 직접 추가됨
        lit_names = {p.name for p in kg.state_patterns["sp_lit"].identity_query_params}
        self.assertIn("search", lit_names)
        # semantic SP에도 suffix 일치로 전파
        sem_names = {p.name for p in kg.state_patterns["sp_sem"].identity_query_params}
        self.assertIn("search", sem_names)

    def test_skip_button_like_inputs(self) -> None:
        from site_adaptive_webagent.kg.types import Action as _Action, LeadsToEdge as _LTE
        from site_adaptive_webagent.kg.seed.post_enrich import (
            backfill_query_params_from_form_actions,
        )
        kg = SiteKG(site="x")
        kg.state_patterns["sp"] = StatePattern(id="sp", url_template="/explore/projects")
        for input_name in ("submit", "_token"):
            name = f"crawl:form:explore_projects:{input_name}"
            kg.actions[name] = _Action(name=name)
            kg.leads_to_edges.append(_LTE(
                from_state_pattern_id="sp",
                action_name=name,
                to_state_pattern_id="sp",
            ))
        backfill_query_params_from_form_actions(kg)
        self.assertEqual(kg.state_patterns["sp"].identity_query_params, [])

    def test_cross_target_form_edge_adds_to_target_state(self) -> None:
        """cross-target (from != to) form edge는 query param을 to state에 박아야 함."""
        from site_adaptive_webagent.kg.types import Action as _Action, LeadsToEdge as _LTE
        from site_adaptive_webagent.kg.seed.post_enrich import (
            backfill_query_params_from_form_actions,
        )
        kg = SiteKG(site="x")
        kg.state_patterns["sp_project"] = StatePattern(
            id="sp_project", url_template="/{project_path}",
        )
        kg.state_patterns["sp_search"] = StatePattern(
            id="sp_search", url_template="/search",
        )
        action_name = "crawl:form:search:search"
        kg.actions[action_name] = _Action(name=action_name)
        kg.leads_to_edges.append(_LTE(
            from_state_pattern_id="sp_project",
            action_name=action_name,
            to_state_pattern_id="sp_search",
        ))
        backfill_query_params_from_form_actions(kg)
        search_names = {p.name for p in kg.state_patterns["sp_search"].identity_query_params}
        self.assertIn("search", search_names)
        project_names = {p.name for p in kg.state_patterns["sp_project"].identity_query_params}
        self.assertNotIn("search", project_names)


class BackfillOptionalBindingsTests(unittest.TestCase):
    def test_query_params_become_optional_bindings(self) -> None:
        from site_adaptive_webagent.kg.seed.post_enrich import backfill_optional_bindings
        kg = SiteKG(site="x")
        kg.state_patterns["sp"] = StatePattern(
            id="sp", url_template="/search",
            identity_query_params=[
                IdentityParam(name="scope", type="enum"),
                IdentityParam(name="search_query", type="string"),
            ],
        )
        it = InfoType(
            name="search_results",
            realizes=[RealizesEdge(infotype="search_results", state_pattern_id="sp")],
        )
        kg.infotypes["search_results"] = it
        backfill_optional_bindings(kg)
        self.assertEqual(set(it.optional_bindings), {"scope", "search_query"})

    def test_required_bindings_not_duplicated(self) -> None:
        from site_adaptive_webagent.kg.seed.post_enrich import backfill_optional_bindings
        kg = SiteKG(site="x")
        kg.state_patterns["sp"] = StatePattern(
            id="sp", url_template="/{project_path}/x",
            path_params={"project_path": {"type": "path_segments"}},
            identity_query_params=[IdentityParam(name="project_path", type="string")],
        )
        it = InfoType(
            name="x", required_bindings=["project_path"],
            realizes=[RealizesEdge(infotype="x", state_pattern_id="sp")],
        )
        kg.infotypes["x"] = it
        backfill_optional_bindings(kg)
        self.assertEqual(it.optional_bindings, [])


class PruneUnusedFormActionsTests(unittest.TestCase):
    def test_unused_form_actions_pruned(self) -> None:
        from site_adaptive_webagent.kg.types import Action as _Action, LeadsToEdge as _LTE
        from site_adaptive_webagent.kg.seed.post_enrich import prune_unused_form_actions
        kg = SiteKG(site="x")
        kg.actions["crawl:form:x:search"] = _Action(name="crawl:form:x:search")
        kg.actions["crawl:form:y:submit"] = _Action(name="crawl:form:y:submit")
        kg.actions["crawl:form:used_action:input"] = _Action(
            name="crawl:form:used_action:input",
        )
        kg.actions["open_page"] = _Action(name="open_page")  # semantic, not crawl:form
        kg.state_patterns["sp1"] = StatePattern(id="sp1", url_template="/a")
        kg.state_patterns["sp2"] = StatePattern(id="sp2", url_template="/b")
        kg.leads_to_edges.append(_LTE(
            from_state_pattern_id="sp1",
            action_name="crawl:form:used_action:input",
            to_state_pattern_id="sp2",
        ))
        removed = prune_unused_form_actions(kg)
        self.assertEqual(removed, 2)
        self.assertNotIn("crawl:form:x:search", kg.actions)
        self.assertNotIn("crawl:form:y:submit", kg.actions)
        self.assertIn("crawl:form:used_action:input", kg.actions)  # 사용됨
        self.assertIn("open_page", kg.actions)  # crawl:form 아님, 건들지 않음


class ActionDescriptionAutoFillTests(unittest.TestCase):
    def test_nav_description(self) -> None:
        from site_adaptive_webagent.kg.types import Action as _Action
        from site_adaptive_webagent.kg.seed.post_enrich import auto_fill_action_descriptions
        kg = SiteKG(site="x")
        kg.actions["crawl:nav"] = _Action(name="crawl:nav")
        auto_fill_action_descriptions(kg)
        self.assertIn("navigation", kg.actions["crawl:nav"].description)

    def test_form_description(self) -> None:
        from site_adaptive_webagent.kg.types import Action as _Action
        from site_adaptive_webagent.kg.seed.post_enrich import auto_fill_action_descriptions
        kg = SiteKG(site="x")
        kg.actions["crawl:form:explore_projects:name"] = _Action(
            name="crawl:form:explore_projects:name",
        )
        auto_fill_action_descriptions(kg)
        desc = kg.actions["crawl:form:explore_projects:name"].description
        self.assertIn("name", desc)
        self.assertIn("/explore/projects", desc)


if __name__ == "__main__":
    unittest.main()
