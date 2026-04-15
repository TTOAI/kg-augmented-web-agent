"""Evaluator package — sub-goal 완료 여부를 검증한다."""

from .base import Evaluator
from .simple import verify_done

__all__ = ["Evaluator", "verify_done"]
