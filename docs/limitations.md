# Limitations

## Scope of KG extraction

**Filter-value inventories** are collected as existence proofs, not as complete enumerations. Our recursive expander reaches the value-list panel and records up to five example values per category, but GitLab's filter UI uses an autocomplete-on-type paradigm where the full inventory is only materialized once the user types. The KG therefore tells the agent that a given filter exists and names its URL parameter, leaving the actual value (e.g. a specific label or username) to be supplied from task context. Sites whose filter options are fully pre-rendered (sort orders, tab states) are captured in full.

**Custom component frameworks that do not expose ARIA roles** (e.g. a `<div>` with a click handler in place of a `<button>`) are invisible to the extractor. Our method relies on the browser's accessibility tree via CDP; components that implement their own event handling without ARIA annotations will not surface.

**URL parameter mapping** for filter categories is read from a site-level config (`config/sites/<site>/class_taxonomy.yaml`) rather than inferred per-crawl. Extending to a new site requires populating this mapping once; on sites without a configured entry, the KG still records the filter category as existing but leaves `param` blank.

## Evaluation surface

**Evaluator strict-match coincidences.** WebArena-Verified scores a task by normalized string comparison of the agent's final answer against a reference. On some tasks (documented in [evaluation/eval_exclusions.md](evaluation/eval_exclusions.md)) both variants produce semantically different answers that collide with the reference, making outcome differences partially driven by coincidence rather than reasoning. We report results with and without these tasks included.

**Per-task variance.** Individual GitLab tasks can flip outcome under LLM sampling noise even at temperature 0; our main measurement uses paired McNemar over a stratified sample to control for this. Small-N reports (e.g. smoke checks) are noise-dominated and are treated only as sanity signals, not as evidence.

## Site coverage

**Two sites.** The method has been applied to GitLab and to a forum site (Reddit/Postmill). A broader cross-site validation would require additional site-specific plugin implementations. The per-site effort is bounded by: one class-taxonomy config file, one plugin implementation of the URL-template derivation, and one crawl-seed list. Nothing else in the pipeline is site-specific.

## Agent-side

**KG hint consumption is advisory.** The agent reads structured hints injected into the observation message. We do not guarantee the agent follows them; we observe empirically that the presence of a correctly-inferred target class reduces exploration steps and that filter-parameter hints enable URL-first strategies on filter-heavy tasks.

**The KG does not make the agent reason better about the task itself.** A task that requires ambiguous multi-step interpretation (e.g. deciding among several issues that match "my latest updated issue with 'homepage content'") depends on the agent's language reasoning; KG hints are silent here.
