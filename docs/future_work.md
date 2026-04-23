# Future work

## Filter-value inventory without typed autocomplete

The recursive expander today records an existence proof and up to five example values per filter category. A complete per-site inventory could be obtained by one of two routes:

- **API scraping via SitePlugin**: for sites that expose a public autocomplete endpoint (GitLab's `/-/autocomplete/users.json`, `/-/autocomplete/labels.json`), the plugin can fetch inventory in a single request. This remains site-specific and belongs in the plugin layer.
- **Observation-layer value harvesting**: when the agent browses an issue-detail page, the visible `Label` / `Assignee` chips reveal values already in use for that namespace. Aggregating these across a namespace produces an inventory without any new crawling. This is site-agnostic but requires the agent to pass observed values back into the KG layer — currently there is no such feedback channel.

## Multi-site generalization

The two-site evidence (GitLab + Postmill) shows the protocol operates on sites with different URL, vocabulary, and UI conventions. A systematic cross-site study over three or more heterogeneous sites (a forum, a code host, and a document-management site, for example) would quantify how much per-site engineering the protocol still requires. Each new site needs a plugin (URL template derivation) and a class-taxonomy config; everything else is shared.

## KG temporal consistency

Sites change — new pages appear, old filters are removed, URL schemes are revised. The current pipeline rebuilds from scratch on each run. A diff-aware rebuild would:
1. Detect class additions and deletions against the previous KG.
2. Flag agent hints that reference since-removed classes so they can be filtered at runtime.
3. Report class-level drift as a summary, giving the paper-audit "the KG was valid during measurement" signal.

## Agent feedback into the KG

Runtime observations (actual labels seen on issue chips, actual assignees on a merge-request page) could populate a value-inventory side table without touching the crawl pipeline. This would turn the KG into a living object that accrues per-namespace knowledge through agent use.

## Deeper integration of reasoning and structure

Current integration is through hint injection into the observation prompt. Alternative integrations to explore:
- A dedicated `consult_kg(target_class)` tool the agent can call explicitly, making the KG lookup auditable at trajectory level.
- A pre-execution pass that derives a KG-based plan skeleton from the task, which the agent either confirms or overrides.

## Evaluator-agnostic scoring

The strict-match evaluator used in WebArena-Verified occasionally gives coincidental credit for semantically wrong answers. A supplementary scorer that checks URL trajectory and interaction trace against a structural specification (reach a `project/issue_detail` whose title matches the target) would decouple "got the right final string" from "reached the right page for the right reason."
