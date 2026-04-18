# Abstract 초안 (한국어 · 영어)

## 한국어

LLM 기반 웹에이전트의 주된 병목은 DOM 관찰 기반 long-horizon planning에 있으며, 표준 ReAct
agent는 사이트 전역의 URL schema·state transition·form constraint 같은 관계적 지식을
활용하지 못한다. 본 연구는 Site-specific Knowledge Graph (SiteKG)를 planning substrate로
결합한 웹에이전트를 제안하고 WebArena-Verified GitLab에서 정량 평가한다. SiteKG는 표준 KG
구성(entity·relation·schema + trust layer)에 웹 특화 요소 (InfoType / StatePattern /
LeadsToEdge)와 4개 hook (plan→info / rewrite / validator / trust update)을 더한다. Playwright
crawl + multi-call LLM derivation + heuristic post-enrichment로 per-task manual labeling
없이 구축 가능한 2-stage automated pipeline을 제공한다 (frozen KG ARI=0.926). 30 task (task
type별 10) × 2 variant × N=3 = 180 runs의 paired McNemar / Wilcoxon 양방향 검정을 통해 (i)
task type별 heterogeneous effect를 정량화하고, (ii) token/step/wall-time compute trade-off를
보고하며, (iii) 구축 pipeline 자체를 재현 가능 artifact로 제공한다.

**핵심어**: Site-specific Knowledge Graph, LLM Web Agent, Planning Substrate, WebArena-Verified,
Heterogeneous Effect, PROV-O

## 영어 (backup)

The primary bottleneck of LLM-based web agents lies in long-horizon planning over DOM
observations: standard ReAct agents cannot exploit site-wide relational knowledge such as URL
schema, state transitions, or form constraints. We propose a web agent augmented with a
Site-specific Knowledge Graph (SiteKG) as planning substrate, and evaluate it on WebArena-Verified
GitLab. SiteKG extends the standard KG formulation (entity / relation / schema + trust layer)
with web-specialized elements (InfoType, StatePattern, LeadsToEdge) and four integration hooks
(plan-to-info, rewrite, validator, trust update). We provide a 2-stage automated construction
pipeline — Playwright crawl plus multi-call LLM derivation with heuristic post-enrichment —
that requires no per-task manual labeling (frozen KG ARI=0.926). Through 180 paired runs
(30 tasks × 2 variants × N=3 repetitions, task-type-stratified), we quantify (i) the
heterogeneous effect of KG across task types using per-type McNemar tests, (ii) the compute
trade-off in tokens / steps / wall-time, and (iii) release the construction pipeline as a
reproducible research artifact.

**Keywords**: Site-specific Knowledge Graph, LLM Web Agent, Planning Substrate,
WebArena-Verified, Heterogeneous Effect, PROV-O

---

## Notes

- 국내 학회 포맷에 따라 한국어/영어 중 택1 또는 둘 다 요구. 최종 투고 시점에 선택.
- 분량 가이드: 한국어 ~200자, 영어 ~150 words (대부분 국내 학회 가이드).
- 결과 확정 후 "KG effect direction"이 확정되면 `abstract_final.md`로 분리 가능.
- 현재는 **부호 가정 없음** 원칙 따라 "quantify"로 표현, "improve/reduce" 표현 금지
  (`docs/08 §2` freeze rule).
