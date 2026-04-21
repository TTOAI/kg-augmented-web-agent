# Research Roadmap

**Purpose**: 연구의 큰 목적을 흔들림 없이 유지하기 위한 reference. 매 작업 결정 전 참조.

---

## 🎯 최종 목적 (바꿀 수 없음)

**WebArena-Verified GitLab 벤치마크에서 LLM 웹에이전트의 task 성공률 향상.**

## 중간 목적

에이전트에게 **구조화된 site knowledge**를 제공해 unseen page·task에서도 근거 있는 행동 가능하게 함.

## 수단 pipeline

```
Stage A: Class-based KG 구축 — node(class) 정의       ← 현재 진행 중
    ↓
Stage B: Action catalog — 각 class에서 가능한 action
    ↓
Stage C: Navigation edge — action → next class
    ↓
Solution 2: KG 위 BFS simulation + agent hint
    ↓
Evaluation: baseline vs KG-assisted agent 비교        ← 최종 goal 측정 지점
```

### Stage A 내부

- **A.0** (완료): V0.1 pipeline sanity, V0.2 Frozen KG inventory
- **A.1** (현재): Sample 확장(23→~60) + rule 일반화
- **A.2**: Rule 추출
- **A.3**: Unseen data test
- **A.4**: 전체 GitLab KG 적용
- **A.g**: Stage A retrospective

## 보조 도구

- **Protocol spec** (`docs/validation/V1_protocol_spec.md`): 분류 process의 reproducibility 보장. Stage A를 원칙 있게 수행하기 위한 도구지 **그 자체가 연구 기여물이 아님**.
- **Deferred issues** (`docs/validation/V1_deferred_issues.md`): Stage B 이후에 다룰 기술 부채 기록.

---

## 자가 검열 질문 (매 작업 전)

1. **이 작업이 최종 목적(agent 성공률 향상)에 기여하는가?**
2. **현재 지점에서 최종 목적까지 가장 짧은 path는 무엇인가?**
3. **이 작업이 보조 도구(protocol spec 등)의 완성도를 추구하는 것은 아닌가?**

## Anti-pattern 경고

다음 흐름이 관찰되면 **즉시 멈추고 재조정**:

- **Protocol 과잉정제** — spec version이 빠르게 올라가는데 실제 pipeline 진행은 정체
- **Yak shaving** — 당면 문제 해결을 위해 부수 작업이 꼬리 물고 늘어남
- **수단 완성도 집착** — class taxonomy·rule·protocol 자체의 세련도 추구 (goal은 agent 성공률)
- **보조 목적 언어로 포장** — "cross-site reproducibility" "reviewer defense" 등이 주장되면, **최종 목적과의 연결**을 재확인

## 원칙 요약

- **목적** = agent 성공률. 고정.
- **수단** = KG + simulation. 고정.
- **방법** = protocol + 측정 반복. 가변 (iterative 확장 허용).
- **완료 기준** = Solution 2 MVP → 벤치마크 성능 차이 측정. 그 전엔 모든 작업이 "means to end".

---

## 다음 checkpoint

- **Stage A.1 완료** — rule 일반화 증거
- **Stage A.4 완료** — 전체 GitLab KG 초안
- **Stage B·C MVP** — 간소 version으로 빠르게 완성
- **Solution 2 proof-of-concept** — 3-5 task 대상
- **최종 평가** — baseline vs KG-assisted 성공률 비교
