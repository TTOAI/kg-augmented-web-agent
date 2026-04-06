from __future__ import annotations

from .enums import ValidationResult
from .types import ValidatorRule


def validate(rules: list[ValidatorRule]) -> ValidationResult:
    """ValidatorRule 목록을 판정한다.

    이번 구현은 rule_type 기반 결정론적 판정만 지원한다:
    - "always_pass"  → PASS
    - "always_fail"  → FAIL
    - 그 외          → PARTIAL

    rules가 비어 있으면 PASS를 반환한다.
    규칙이 여러 개일 때 FAIL이 하나라도 있으면 FAIL, PARTIAL이 있으면 PARTIAL, 전부 PASS면 PASS.
    """
    if not rules:
        return ValidationResult.PASS

    results = [_evaluate_rule(rule) for rule in rules]

    if ValidationResult.FAIL in results:
        return ValidationResult.FAIL
    if ValidationResult.PARTIAL in results:
        return ValidationResult.PARTIAL
    return ValidationResult.PASS


def _evaluate_rule(rule: ValidatorRule) -> ValidationResult:
    if rule.rule_type == "always_pass":
        return ValidationResult.PASS
    if rule.rule_type == "always_fail":
        return ValidationResult.FAIL
    # llm_judge, element_visible, text_contains, url_matches 등 실행 컨텍스트가
    # 필요한 규칙은 현재 stub에서 PARTIAL로 처리한다.
    return ValidationResult.PARTIAL
