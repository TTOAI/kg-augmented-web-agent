"""Runtime 인터페이스 — 에이전트가 브라우저/환경과 상호작용하는 얇은 계약.

구체 구현은 playwright_runtime.py와 mock_runtime.py에 둔다.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..types import PageObservation


@runtime_checkable
class Runtime(Protocol):
    """에이전트가 호출하는 브라우저 액션 계약."""

    async def observe(self, page: Any) -> PageObservation: ...

    async def click(self, page: Any, target: str, url_hint: str = "", element_type: str = "") -> dict: ...

    async def fill(self, page: Any, target: str, value: str, submit: bool = False) -> dict: ...

    async def search(self, page: Any, query: str) -> dict: ...
