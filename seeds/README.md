# Seeds — SiteKG 시드 데이터

## 시드 작성 5원칙

1. **KG에 description 필드 없음** — task-specific hint가 구조적으로 불가능
2. **side_effects는 관찰 가능한 행동 결과만** — "URL gains ?sort=desc" (OK), "task가 성공한다" (NG)
3. **visibility_condition은 경험으로만 아는 조건만** — "after click search input" (OK)
4. **모든 정보는 task를 모른 채 사이트를 탐색한 Playwright가 수집 가능해야**
5. **widget_key는 사람 가독 이름** OK, 그러나 LLM에게는 DOM 속성을 제공

## 파일 구조

- `{site}.auto.yaml` — `seed_collector.py`가 자동 생성한 raw 시드
- `{site}.yaml` — 사람이 검증/편집한 확정 시드
- `.auth_state.json` — Playwright 인증 state (gitignore 대상)

## 시드 생성 방법

```bash
# 자동 수집 (~1-2분)
python -c "
import asyncio
from site_adaptive_webagent.runtime.sitekg.seed_collector import collect_site_kg, dump_yaml

async def main():
    sitekg = await collect_site_kg(
        base_url='http://localhost:8023',
        site_id='gitlab',
        auth_storage_state='seeds/.auth_state.json',
    )
    dump_yaml(sitekg, 'seeds/gitlab.auto.yaml')

asyncio.run(main())
"

# 사람 검증 후 확정
cp seeds/gitlab.auto.yaml seeds/gitlab.yaml
# 편집: false positive 제거, widget_key 정리
```
