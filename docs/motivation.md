# Why a site knowledge graph

## The gap we address

An LLM-based web agent operating on a live site must, for every sub-goal, answer three questions:

1. **Where should I navigate next?** — which page class serves this sub-goal.
2. **What interactions does that page offer?** — which buttons, filters, and URL parameters exist.
3. **How do I shape the URL to reach the state the task implies?** — which `?param=value` combinations are even possible on this site.

Pure LLM agents discover answers to these three questions at execution time by reading the current observation. This is expensive (each discovery step is a round trip to the LLM), noisy (the agent frequently hallucinates parameters or misreads a component's semantics), and **re-discovered from scratch on every task**.

A site KG externalizes the answers: it is a **per-site structural model** that the agent can consult at runtime. The KG is:

- **Pre-computed**, so the agent does not spend LLM calls rediscovering page structure.
- **Consistent across tasks**, so the answer for "what filters does the issue-list page offer?" does not vary by run.
- **Inspectable and replaceable**, so its content and limits can be audited independently of the agent.

## What a site KG contains

Our KG stores, for each class of pages a site exposes:

- A **URL template** with identified path parameters (e.g. `/{namespace}/{project}/-/issues`).
- A structured **role description** — scope (user / entity / admin / site), trigger intent phrases, and disambiguators used by the agent's target-class inferrer.
- An **action catalog** — navigation links, in-page controls, and filter dropdown categories with their URL parameters (e.g. `Label → label_name[]`).
- A **class-to-class edge graph** — observed transitions between page classes, with trust levels.

The KG is produced by a fixed site-agnostic protocol (see [method/kg_protocol.md](method/kg_protocol.md)); the same protocol, when applied to a different site, yields that site's KG under its own vocabulary.

## What the KG is not

- It is not a complete enumeration of every value a user might ever type into a filter. Filter-value autocomplete suggestions that require typed input are out of scope by design — these belong to the agent's task context, not the KG.
- It is not a hand-curated ontology. Classes, actions, and edges come from automated crawling plus a single annotation pass; no class-by-class human labeling.
- It is not a replacement for the agent's language understanding. The KG answers "where and how," and the agent decides "which value to type" from the task.

## What we claim

The contribution validated by the experiments in this repository:

1. A site-agnostic protocol for building such a KG, with a worked example on GitLab and a second application on a forum site (Reddit/Postmill) that shares no URL or vocabulary conventions with GitLab.
2. An agent integration that consumes the KG through structured hints injected into the observation, without requiring bespoke tools or changes to the action schema.
3. An empirical comparison of the agent's task success with and without KG hints on a fixed task set, with full disclosure of evaluator-level noise (task outcomes that succeed by coincidence under strict-match scoring).
