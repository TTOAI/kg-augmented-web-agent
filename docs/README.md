# Site-Adaptive Web Agent — KG-assisted navigation

A web agent that consults a **site knowledge graph (KG)** at runtime to decide where to go, which filters are available, and how to shape a URL for a given sub-goal. The KG is built from the target site itself via a site-agnostic discovery protocol.

## Why a KG

`motivation.md` — the problem this addresses and why a per-site structural model is the right object to build.

## How the KG is built and consumed

| Topic | Document |
|---|---|
| Class discovery protocol (site-agnostic) | [method/kg_protocol.md](method/kg_protocol.md) |
| KG schema — classes, actions, edges, descriptions | (see Stage reports below) |
| Stage A: URL classification rules | [method/stage_a_rules.md](method/stage_a_rules.md) |
| Stage B: action catalog + filter categories | [method/stage_b_action_catalog.md](method/stage_b_action_catalog.md) |
| Stage C: class-to-class edge graph | [method/stage_c_edge_graph.md](method/stage_c_edge_graph.md) |
| Agent integration (task inferrer, path finder, hint generator) | runtime source in `site_adaptive_webagent/kg/runtime/` |
| Site portability (config split + plugin) | `config/sites/<site>/class_taxonomy.yaml` + `site_adaptive_webagent/kg/site_plugin.py` |

## Evaluation

| Topic | Document |
|---|---|
| Task selection, metrics, and exclusions | [evaluation/eval_exclusions.md](evaluation/eval_exclusions.md) |
| Results | `evaluation/results.md` (populated by main measurement) |

## Rebuilding the KG

```bash
# GitLab (default)
webarena-verified env start --site gitlab --port 8023 --env-ctrl-port 8024
python -m scripts.kg.utils.refresh_auth
python -m scripts.kg.build.crawl
python -m scripts.kg.build.classify_rules
python -m scripts.kg.build.collect_actions
python -m scripts.kg.build.action_catalog
python -m scripts.kg.build.edge_graph
python scripts/kg/build/class_catalog.py
```

Output lands in `output/validation/` (site-agnostic path; renamed incrementally). The runtime agent reads `output/validation/kg_solution/class_descriptions.json`.

## Limitations and future work

[limitations.md](limitations.md) — what the KG does not model today, and why.

[future_work.md](future_work.md) — planned extensions.

## Archive

[archive/](archive/) — prior design iterations, lab notes, weekly reports. Kept for reproducibility and citation; not required to understand the current system.
