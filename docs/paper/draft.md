# Site-specific Knowledge Graph를 결합한 LLM 웹에이전트의 Task Type별 효과 정량화

**draft (pre-result, 2026-04-17)** — Table 1 숫자와 §4 Result 본문은 `run_phase_c_180.sh`
종료 후 `scripts/run_analysis.sh`로 자동 채움. 숫자 placeholder는 `{{...}}`로 표시.

---

## §1. Introduction

LLM을 기반으로 한 웹에이전트는 자연어 목표를 받아 브라우저 관찰·행동 계획·실행을
반복하는 폐루프 시스템이다. 최근 연구들은 agent의 주된 병목이 DOM 기반 *grounding*보다
long-horizon *planning*에 있음을 시사한다 [web_01]. 그러나 표준 ReAct-style agent [agent_02]는
매 스텝의 DOM observation에 의존해 계획을 세우므로, 사이트 전역의 URL schema·state
transition·form constraint 같은 *관계적 지식*을 활용하지 못한다. 결과적으로 (i) navigation
경로 중복 탐색, (ii) URL parameter 구성 실수, (iii) post-condition 확인 누락 같은 실패 패턴이
반복된다.

기존 대응으로는 trajectory 기반 workflow memory [AWM]와 context-aware guideline [AutoGuide]이
있으나, 둘 다 자연어 prompt injection 계열로 **구조화된 planning operator**로 기능하지 않는다.
GraphRAG [kg_03]는 관계 중심 질의를 지원하지만 출력이 text QA에 맞춰져 있어 agent action에
직접 쓸 수 없다.

본 연구는 **Site-specific Knowledge Graph (SiteKG)**를 planning substrate로 결합한
웹에이전트를 제안한다. SiteKG는 표준 KG 구성(entity/relation/schema + trust layer)에 웹
환경 특화 요소를 더한다:
- **InfoType** (도메인 명사) + **StatePattern** (URL template + identity params) +
  **LeadsToEdge** (action transitions)
- **Trust layer** (verified/declared/inferred) + **source** (crawl/llm/manual) — PROV-O 기반
- **4 Hooks**로 ReAct 루프에 주입 (A: plan→info / B: rewrite / C: validator / D: trust update)

이 구조를 WebArena-Verified GitLab에서 정량 평가한다. 본 연구의 contribution은 다음 3개다:

> **C1 (Heterogeneous effect)**: Site-specific KG가 LLM web-agent의 task 성공률에 task type별
> (NAVIGATE / RETRIEVE / MUTATE) 어떤 heterogeneous effect를 미치는지 정량화한다 (30 task,
> per-type 10, 2 variant, N=3, per-type paired McNemar).
>
> **C2 (Compute trade-off)**: KG가 token/step/wall-time compute 자원에 미치는 영향을 task type별로
> 보고한다.
>
> **C3 (Methodology artifact)**: Playwright crawl + multi-call LLM derivation + heuristic
> post-enrichment로 구성된 2-stage automated KG 구축 파이프라인을 per-task manual labeling
> 없이 재현 가능한 artifact로 제공한다 (frozen KG ARI=0.926).

**Scope**: GitLab 단일 사이트, per-type 균등 샘플링 30 task, Baseline vs Full KG 2-variant,
N=3 반복. 부호 가정 없는 양방향 H1a (정확도) · H1b (효율) 검정.

---

## §2. Related Work

**Trajectory memory / guideline**. AWM [AWM]은 과거 trajectory에서 재사용 workflow를 추출해
prompt에 주입한다. AutoGuide [AutoGuide]는 context-aware 자연어 guideline을 추출한다. 두
접근 모두 *자연어 retrieval-augmented memory*로, structural graph operator가 아니다. 본 연구는
formal StatePattern/Action graph를 plan 재구조화 operator로 사용한다는 점에서 다르다.

**Graph-based retrieval**. GraphRAG [kg_03]는 텍스트 그래프 기반 multi-hop QA를 지원하지만,
출력이 question answering이다. 본 연구는 동일한 관계 중심 retrieval을 *행동 계획*에 적용한다.

**Web agent planning**. Tree Search [Koh'24]는 runtime branching을, WebDreamer [Gu'24]는 LLM
world-model simulation을 사용한다. 본 연구는 사전 구축된 명시적 state graph로 runtime 탐색을
축약한다. AgentOccam [Zhu'24]은 관측·행동 공간 정렬만으로 충분하다고 주장하지만, 이는
site-specific structural knowledge의 필요성에 대한 직접적 반명제로, 본 연구가 empirical하게
다룬다.

---

## §3. Method

### 3.1 Baseline — Standard ReAct with justified modifications

Baseline agent는 WebArena/Visual-WebArena 관례의 ReAct 루프 (observe → plan → tool-use →
verify)를 따른다. 실험 재현성·안정성·공정 비교를 위한 최소 수정을 4 카테고리로 공개한다
(`docs/kg_design/07 §5-1`):

- **(A) Standard adherence**: Observe→plan→tool-use→verify loop, generic tool-based action,
  DOM-based `observe_page`, checkpoint URL rollback.
- **(B) Justified deviation**: `goal_type` 기반 sub-goal decomposition (NAVIGATE의 hard rule 필요),
  enum-제한 `declare_error` (impossible task 명시 선언으로 false-negative 감소), LLM-기반
  `classify_task_type` (regex 오분류 케이스 보완), hard-rule `_verify_done` (final navigation
  URL 미변경 감지만 유지).
- **(C) Engineering necessity**: `LLM_TEMPERATURE=0` (재현성), retry/step budget (stuck 방지),
  `_MAX_LLM_CALLS_PER_TASK=350` (retry-loop 폭발 방지, smoke 관찰 max 275의 27% buffer),
  `_CountingLLMClient` wrapper (양 variant 동일 적용).
- **(D) Over-engineering removed**: 이전 `_verify_done` LLM 재호출은 task당 call 2배화 +
  verifier가 context 일부만 보아 false reject 유발 → 표준 ReAct로 되돌려 hard rule만 유지.

### 3.2 SiteKG schema

노드: **InfoType** (도메인 명사, 예: `issues_filtered`), **StatePattern** (URL template +
identity params, 예: `/{project}/-/issues?state={state}&label_name[]={label}`).
엣지: **realizes** (InfoType → StatePattern), **LeadsToEdge** (StatePattern → StatePattern via
action), **uses_binding** (InfoType → binding slot).
Trust layer: **verified** (crawl-observed) > **declared** (manual) > **inferred** (LLM-derived +
heuristic enrichment). Source: `crawl`/`llm`/`manual` (PROV-O).

### 3.3 2-stage automated construction + post-enrichment

SiteKG를 per-task manual labeling 없이 구축한다:

1. **Stage 1 — Playwright seeded crawl** (`source=crawl`, `trust=verified`): 8개 공식 navigation
   entry point에서 출발해 DOM·navigation·URL schema를 관찰. Download extension blocklist, form
   action_url 기반 cross-target edge 등 generic web-engineering prior만 사용 (site vocabulary
   박지 않음).
2. **Stage 2 — Multi-call LLM derivation** (`source=llm`, `trust=inferred`): Reasoning model의
   single-call context overflow 방지를 위해 3 call로 분할 — (1) state pattern grouping,
   (2) InfoType naming + realize edges, (3) action renames. gpt-5.4 + Responses API +
   `reasoning_effort=low`.
3. **Stage 2.5 — Heuristic post-enrichment** (LLM 재호출 0): binding_map, path_params,
   query_params, InfoType category fallback을 일반 URL convention prior로 채움.

**재현성**: 3 derivation run의 group-level ARI mean = **0.926** (run-to-run consistency). Frozen
artifact: `config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json` (git_rev `534c49d`,
builder `0.1.0-hybrid`, 37 InfoType, 3040 StatePattern, 26503 LeadsToEdge, manual=0). 본
evaluation에서 manual stage는 **수행하지 않음**.

### 3.4 Integration via 4 hooks

ReAct 루프에 4 hook 주입:
- **Hook A (plan→info)**: intent + task_type → `(InfoType, bindings)` lookup via enum-제약 JSON
  tool use. Tool schema가 각 InfoType의 path_slots (namespace, project_path, ref 등)을
  명시해 LLM이 path slot까지 bindings에 포함하도록 유도. 추가로 runtime context auto-fill
  (executor가 현재 page URL → path_slots 자동 추출)이 `emit_target_url`의 fallback 역할.
- **Hook B (rewrite)**: sub-goal list를 trust-permissive하게 재구조화. Trust policy는
  verified / declared / inferred 전부 수용 (2026-04-18 Option B, `07 §14`). Incomplete
  URL (unfilled path slot) 만 guard로 skip.
- **Hook C (validator)**: `current_url`이 target StatePattern에 `state_matches`하면 early
  termination. 단 **NAVIGATE task에서만 발동** (RETRIEVE/MUTATE는 data 추출 / form submit
  필요 → suppress, `05 §5`).
- **Hook D (trust update, logging only)**: path·result 기록. Trust 변동은 본 evaluation에서
  disabled (continual adaptation은 future work; `07 §11`).

Baseline variant는 4 hook 모두 off (`KG_VARIANT=off`), Full KG는 A/B/C on + D logging-only
(`KG_VARIANT=full`, `SITEKG_ENABLED=1`). 동일 codebase·LLM (gpt-5.4-mini)·temperature·task
세트 → internal validity 확보.

---

## §4. Experiment & Result

### 4.1 Setup

- **Tasks**: WebArena-Verified GitLab 180 task 모집단에서 per-type equal random sampling
  (seed=42), 각 10개 × 3 types = 30 task. 목록은 부록 참조.
- **Variants**: Baseline (KG off) vs Full KG (Hook A/B/C on).
- **Repetition**: N=3 per (variant, task).
- **Model**: gpt-5.4-mini, `LLM_TEMPERATURE=0`.
- **Infrastructure**: Playwright Chromium, Docker `webarena/gitlab-v1.15-verified`.
- **Statistics**: H1a paired McNemar (binary success), H1b Wilcoxon signed-rank (token/step/
  wall-time). Overall α=0.05, per-type Bonferroni α=0.0167 (3 types). Wilson 95% CI.
- **Binarization**: Per (variant, task), 3 run의 majority vote로 paired binary 결정
  (`06 §4-5`).
- **Broken eval handling**: Evaluator strict-match 결함으로 정상 행동이 fail 기록되는 task는
  `eval_exclusions.md` 목록에 따라 **내부 성공** 기록 + adjusted 수치 별도 보고.

### 4.2 Overall results (Table 1, per-type breakdown)

`{{TBD — populated by scripts/make_paper_tables.py after measurement}}`

| Task Type | N | Baseline SR (95% CI) | Full KG SR (95% CI) | McNemar p | OR |
|---|---|---|---|---|---|
| Overall  | 30 | `{{b_overall}}` | `{{k_overall}}` | `{{p_overall}}` | `{{or_overall}}` |
| NAVIGATE | 10 | `{{b_nav}}` | `{{k_nav}}` | `{{p_nav}}` | `{{or_nav}}` |
| RETRIEVE | 10 | `{{b_ret}}` | `{{k_ret}}` | `{{p_ret}}` | `{{or_ret}}` |
| MUTATE   | 10 | `{{b_mut}}` | `{{k_mut}}` | `{{p_mut}}` | `{{or_mut}}` |

### 4.3 Heterogeneous effect by task type

`{{TBD — narrative selected from docs/08 §1-2 matrix after result determines which pattern
(Uniform positive / Uniform null / Heterogeneous / Selective positive)}}`.

### 4.4 Efficiency trade-off

Token / step / wall-time per (variant, type). Wilcoxon signed-rank p-value.

| Metric | Baseline | Full KG | Wilcoxon p |
|---|---|---|---|
| Tokens (mean) | `{{...}}` | `{{...}}` | `{{...}}` |
| Steps (mean)  | `{{...}}` | `{{...}}` | `{{...}}` |
| Wall-time (s) | `{{...}}` | `{{...}}` | `{{...}}` |

### 4.5 KG-addressable coverage + Failure mode

`{{TBD — coverage.py per-type Hook A success rate + failure_mode.py P/R/G/A/O labeling with
Cohen's κ}}`.

---

## §5. Limitations

본 연구의 scope는 국내 3-page 논문으로 제한되며, 다음 항목은 명시적 future work이다
(`07 §11`):

- **Compute-matched ablation**: 2-variant 설계는 KG *정보* 효과와 추가 LLM call의 reasoning-step
  효과를 완전 분리하지 못한다. Token/step 수치 보고로 partial 차단하되, KG-Info-Ignored
  variant를 포함한 3-variant ablation은 future work.
- **Single-site generalization**: GitLab만 평가. Reddit/Shopping/Map 등 다른 WebArena 사이트로의
  cross-domain 일반화는 future work.
- **Sample size**: 30 task (per-type 10), N=3은 exploratory sample. 더 큰 N은 future work.
- **Fine-grained hook ablation**: Rewrite / validator / trust policy 개별 기여 분리는 future work.
- **Model size robustness**: gpt-5.4-mini 단일 모델. 큰 모델에서의 robustness는 future work.
- **Continual adaptation**: Hook D trust evolution은 architecture에 포함되나 single-shot 평가만
  수행. Longitudinal replay는 future work.
- **KG catalog seed dependence**: KG-addressable coverage는 seed URL 선정에 의존. 본 연구는
  사이트 공식 navigation entry 8개 사용; alternative seed set robustness는 future work.
- **Domain prior in pipeline**: Pipeline 코드 (post-enrichment heuristic, download blocklist)와
  LLM prompt (list/index page convention)에 generic web-engineering prior가 박혀 있음. 이는
  *per-task labeling*이 아닌 *generic knowledge*이며, site vocabulary는 박지 않음
  (`07 §14` disclosure table 참조).

---

## §6. References

- [kg_01] Hogan et al., "Knowledge Graphs," ACM Computing Surveys, 2021.
- [kg_02] Pan et al., "Unifying Large Language Models and Knowledge Graphs: A Roadmap," 2024.
- [kg_03] Edge et al., "From Local to Global: A Graph RAG Approach to Query-Focused Summarization,"
  Microsoft Research, 2024.
- [web_01] Ning et al., "From Grounding to Planning: Web Agents at Scale," 2024.
- [web_02] (Web Agent 5-block reference architecture survey, cited in `01_references_summary.md` §3).
- [web_03] (Web Agent 6 architecture branches survey, cited in `01_references_summary.md` §3).
- [AWM] Wang et al., "Agent Workflow Memory," 2024.
- [AutoGuide] Fu et al., "AutoGuide: Automated Generation and Selection of Context-Aware
  Guidelines for Large Language Model Agents," 2024.
- [Reflexion] Shinn et al., "Reflexion: Language Agents with Verbal Reinforcement Learning," 2023.
- [Koh'24] Koh et al., "Tree Search for Language Model Agents," 2024.
- [Gu'24] Gu et al., "WebDreamer: Model-Based Planning for Web Agents," 2024.
- [Zhu'24] Zhu et al., "AgentOccam: A Simple Yet Strong Baseline for LLM-Based Web Agents," 2024.
- [agent_02] (Agent standard architecture reference, `01 §2`).

(최종 학회 포맷 bibtex 변환은 논문 투고 시점에 수행.)

---

## Placeholders 요약 (측정 종료 후 치환 대상)

- `{{b_*}}`, `{{k_*}}`, `{{p_*}}`, `{{or_*}}` — Table 1 값 (10 cell × 4 col = 40)
- §4.3 narrative — `docs/08 §1-2`의 4 heterogeneous pattern 중 측정 결과에 맞는 것 선택
- §4.4 Table — Token/Step/Wall-time (3 row × 3 col = 9)
- §4.5 coverage/failure-mode 수치 + Cohen's κ

치환은 `scripts/make_paper_tables.py` (P1-2)가 자동 수행.
