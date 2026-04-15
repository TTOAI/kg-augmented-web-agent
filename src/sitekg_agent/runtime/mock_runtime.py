"""테스트용 in-memory Runtime 구현 (스켈레톤).

실제 테스트에서는 tests/fixtures.py의 FakePage 계열을 직접 사용하거나,
여기를 확장해 독립 모듈로 발전시킨다.
"""
from __future__ import annotations

from typing import Any

from ..types import PageObservation


class MockRuntime:
    """아직 실제 동작 없음 — 테스트에서 필요할 때 채운다."""

    async def observe(self, page: Any) -> PageObservation:
        raise NotImplementedError

    async def click(self, page: Any, target: str, url_hint: str = "", element_type: str = "") -> dict:
        raise NotImplementedError

    async def fill(self, page: Any, target: str, value: str, submit: bool = False) -> dict:
        raise NotImplementedError

    async def search(self, page: Any, query: str) -> dict:
        raise NotImplementedError
