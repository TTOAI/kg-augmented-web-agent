# 10. Phase C 결함 Postmortem — KG 미활성화로 인한 무효 측정

## 사건 개요

2026-04-17 Phase C 180 runs 측정 완료 후 `scripts/run_analysis.sh`로 분석한 결과,
Baseline과 Full KG variant의 task success rate가 **완전 동일**하게 나왔다:

- Overall: Baseline **20%** (6/30) = Full KG **20%** (6/30)
- NAVIGATE: 20% = 20% / RETRIEVE: 30% = 30% / MUTATE: 10% = 10%
- McNemar exact two-tailed p = 1.0000, 모든 per-type/Wilcoxon metric p > 0.6

원인 추적 결과 **kg_full variant가 실제로는 Hook A/B/C를 전혀 실행하지 않고 baseline과
동일한 agent 경로로 돌았음**이 확인됐다. Phase C 측정 자체는 **kg_full vs baseline이
아닌 baseline vs baseline 비교**에 불과했다.

---

## 근본 원인

### 1차 원인 — 스크립트 환경 변수 누락

`run_phase_c_180.sh` / `run_phase_c_recovery.sh` / `run_phase_c_mini_recovery.sh` 3개
스크립트 모두에서 **`SITEKG_ENABLED=1` 환경 변수 누락**. `KG_VARIANT=full` +
`SITEKG_FROZEN=...`만 설정됨.

### 2차 — 다단 guard gate 실패

1. **adapter.py** (`_maybe_load_kg_context`, lines 270-294):
   ```python
   if os.getenv("SITEKG_ENABLED") != "1":
       return None  # KG 미활성 모드 — kg_context=None
   ```
   → `SITEKG_ENABLED`가 "1"이 아니면 즉시 None 반환.

2. **agent/core.py** (`run_agent`, line 65):
   ```python
   if kg_context is not None and kg_variant in {"info_ignored", "full"}:
       # Hook A 진입
   ```
   → kg_context=None이면 KG_VARIANT=full이어도 Hook A 조건 실패 → baseline path.

결과: Hook A/B/C 전부 skip, `[KG]` 로그 라인 emission 0건.

### 증거

| 항목 | Baseline | Full KG | Expected if KG worked |
|---|---|---|---|
| `[KG]` log lines (90 runs) | 0 | **0** | > 0 per kg_full run |
| SR Overall | 20% | **20%** (identical) | 차이 있어야 |
| Task 44 steps | 11 | **11** (identical) | 차이 가능 |

---

## 과거 측정 — smoke_kg4에서는 KG 작동했음 (역사적 확인)

결함 원인 재구성 시 중요: 2026-04-16 21:52 ad-hoc smoke `output/smoke_kg4_20260416_215213/`
에서는 **KG가 정상 작동**한 기록 존재.

```
[21:52:20] [KG] loaded frozen snapshot config/sites/gitlab/frozen_kg/2026-04-16T05-34-29Z.json (git_rev=13cbfb9)
[21:52:20] [KG] loaded KGContext for site=gitlab (infotypes=46)
[21:52:23] [KG] Hook A: infotype=project_starrers bindings={}
[21:52:24] [KG] rewrite skipped: trust=inferred (edge.trust=inferred, url_template_trust=inferred)
[21:53:43] [KG] target_reached at step=24 — early SUCCESS (infotype=project_starrers)
```

즉 **KG 로직 자체는 이미 검증된 상태였고**, 2026-04-17 `run_phase_c_180.sh` 작성 과정에서
기존 ad-hoc 실행 환경의 `SITEKG_ENABLED=1`을 이관하지 못한 script regression.

→ **교훈 강화**: 신규 script 작성 시 기존 작동 script의 env var set을 diff로 검증하는
절차 부재.

---

## 유사 결함 범위 (전수 조사)

모든 `.sh` 스크립트에서 `SITEKG_ENABLED=1` 설정 0건:

| script | SITEKG_ENABLED | KG_VARIANT | SITEKG_FROZEN | KG 사용 의도 |
|---|---|---|---|---|
| `run_phase_c_180.sh` | **0** | 1 | 2 | YES (kg_full variant) |
| `run_phase_c_recovery.sh` | **0** | 1 | 2 | YES |
| `run_phase_c_mini_recovery.sh` | **0** | 1 | 1 | YES |
| `run_smoke_phase0c.sh` | **0** | 1 | 1 | YES (smoke) |
| `run_baseline_clean_n1.sh` | 0 | 0 | 0 | NO (baseline only) |
| `run_baseline_n3.sh` | 0 | 0 | 0 | NO |
| `run_phase2_baseline.sh` | 0 | 0 | 0 | NO |
| `run_smoke_14.sh`, `run_smoke_n3.sh` | 0 | 0 | 0 | NO |

**KG를 의도했던 4개 스크립트 (Phase C 3개 + Phase 0c smoke) 전부에 같은 결함**.
Phase 0c smoke 당시 "task 46이 kg_full에서 성공"이라고 해석했던 것도 **실제로는 KG
없이 baseline path로 돈 결과**였음. 즉 Phase 0c → Phase C 내내 kg_full variant는
한 번도 Hook을 실행한 적이 없다.

---

## 영향 범위 분류

| 데이터 | 의도 동작 | 실제 동작 | 유효성 |
|---|---|---|---|
| baseline 90 runs (N=1~3) | Hook off | Hook off (동일 path) | ✅ **유효** |
| kg_full 90 runs (N=1~3) | Hook A/B/C on | Hook 전부 off | ❌ **무효** |
| Phase 0c smoke (kg_full 5 task) | Hook A/B/C on | Hook off | ❌ 재해석 필요 |

### Baseline 유효성 근거

- `_maybe_load_kg_context()`가 `SITEKG_ENABLED!=1`일 때 None 반환 → baseline 의도와 동일 동작.
- baseline 90 runs는 SITEKG_ENABLED=0 + KG_VARIANT=off 조합이지만, 의도대로 Hook 없이
  실행됐음 (agent path identical to intended baseline).
- Baseline의 **Agent SUCCESS 71/90 (79%) vs Eval SUCCESS 18/90 (20%)** 및
  per-type/N=3 stability 통계는 self-consistent → 재측정 불필요.

### kg_full 재측정 스코프

- 전체 90 runs (30 task × N=3) 모두 재실행 필요.
- 예상 소요: ~7h overnight (이전 Phase C recovery pace 기준).
- 기존 kg_full 디렉토리는 `output/phase_c_180_contaminated/kg_full_hooks_off/`로 이동.

---

## 추가 sanity 결과 (결함 없음 확인)

### Hook 로직 (코드 자체)
- `agent/core.py` KG_VARIANT dispatch 조건은 **설계대로** — kg_context=None 시 skip은
  intended 방어. 코드 자체 결함 아님.
- `classify_intent_via_kg` (Hook A), `load_kg_context` 함수 존재 + signature OK.

### Frozen KG 무결성
- `config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json` 존재, 12.3 MB, JSON valid.
- Metadata: `source_mix={crawl: 33150, llm: 593, manual: 0}`, git_rev `534c49d`,
  builder_version `0.1.0-hybrid`, ARI mean 0.9264 (3 runs) 기록.

### Baseline 데이터 일관성
- Per-type SR 분포 (MUT 10% < NAV 20% < RET 30%): 난이도 경향과 부합.
- N=3 stability: all-3-succ 4 / all-3-fail 22 / mixed 4 — reasonable run-to-run variance.
- Agent/Eval gap 53건 = NetworkEventEvaluator only 35 + AgentResponseEvaluator only 18 —
  broken eval 검증 대상 (Phase 3).

---

## 대응 계획 (요약)

이번 결함에 대한 전체 대응은 별도 plan 파일 (`/Users/ttoai/.claude/plans/
joyful-moseying-diffie.md`) Phase 2 이후에 정의. 요약:

1. **Phase 2** (재측정): 스크립트 3개 fix + kg_full 90 runs 재실행 + baseline 재사용
2. **Phase 3** (broken eval): baseline 53건 수동·자동 검증 → `eval_exclusions.md` 채움
3. **Phase 4** (분석 + 개선): 재측정 결과로 시나리오 판정 + 개선 축 검토

각 Phase 완료 후 4축 (설계 / 결함 / 완성도 / reviewer) 자체 평가로 다음 Phase 재계획.

---

## 논문 서술에서 언급할 항목 (§5 Limitations 또는 Appendix)

학회 제출본에서 결함을 숨기지 않는 정직성 원칙 (`feedback_be_honest`) 준수:

- **Dev log / pre-final measurement**: 첫 Phase C 측정(2026-04-17)은 kg_full variant의
  환경 변수 누락으로 무효 측정이 됐음. 본문 결과는 Phase 2 재측정 데이터 기준.
- **재현성 문서**에 `SITEKG_ENABLED=1` 요구 명시 (`docs/kg_design/09_reproducibility.md`).
- **Reviewer-proof**: 이 postmortem이 git history에 남아 "결과 보고 후 변경" 의심 차단.

---

## 교훈

1. **측정 스크립트는 dry-run으로 KG emission 로그 확인 필수**. env 변수 누락은 silent
   fallback으로 숨겨짐.
2. **Silent fallback 대신 fail-loud 전환 검토**: `KG_VARIANT=full`인데 kg_context=None이면
   warning 대신 agent를 중단시키는 게 더 안전. 다만 이는 별도 code change (`07 §5-1
   Over-engineering removed` 정책 고려).
3. **Coverage 0%는 즉각적 red flag**: 재측정 전에 `coverage.md`를 반드시 체크.
4. **스크립트 audit 필요**: 동일 패턴 누락이 9개 스크립트 중 4개에서 발견. code review
   checklist에 `SITEKG_ENABLED` 체크 포함.
