"""에피소드 메모리 — 한 task 실행 중 누적되는 메모 리스트의 얇은 래퍼."""
from __future__ import annotations


class EpisodicMemory:
    """task 실행 동안 모이는 자유 텍스트 노트."""

    def __init__(self) -> None:
        self._notes: list[str] = []

    def append(self, note: str) -> None:
        if note:
            self._notes.append(note)

    def as_list(self) -> list[str]:
        return list(self._notes)

    def __len__(self) -> int:
        return len(self._notes)

    def __iter__(self):
        return iter(self._notes)
