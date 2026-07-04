from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.strategies import CountStrategy, StreakStrategy, compute_streak


def _d(offset: int, today: date) -> date:
    return today - timedelta(days=offset)


def test_compute_streak_empty_is_zero() -> None:
    today = date(2026, 7, 4)
    assert compute_streak(set(), today) == (0, 0)


def test_compute_streak_run_ending_today() -> None:
    today = date(2026, 7, 4)
    days = {_d(0, today), _d(1, today), _d(2, today)}
    assert compute_streak(days, today) == (3, 3)


def test_compute_streak_grace_day_yesterday_still_current() -> None:
    """No event *yet* today shouldn't break a streak that ran through
    yesterday — the day isn't over yet, per the documented grace rule.
    """
    today = date(2026, 7, 4)
    days = {_d(1, today), _d(2, today), _d(3, today)}
    current, best = compute_streak(days, today)
    assert current == 3
    assert best == 3


def test_compute_streak_broken_by_two_day_gap() -> None:
    today = date(2026, 7, 4)
    days = {_d(3, today), _d(4, today), _d(5, today)}  # last active 3 days ago
    current, best = compute_streak(days, today)
    assert current == 0
    assert best == 3


def test_compute_streak_best_survives_a_broken_current() -> None:
    today = date(2026, 7, 4)
    # A 4-day run long ago, then an isolated day yesterday (current == 1).
    days = {
        _d(1, today),
        _d(20, today),
        _d(21, today),
        _d(22, today),
        _d(23, today),
    }
    current, best = compute_streak(days, today)
    assert current == 1
    assert best == 4


def test_count_strategy_rejects_missing_target() -> None:
    with pytest.raises(ValueError, match="target"):
        CountStrategy().validate_config({})


def test_count_strategy_rejects_non_positive_target() -> None:
    with pytest.raises(ValueError, match="target"):
        CountStrategy().validate_config({"target": 0})


def test_streak_strategy_rejects_missing_length() -> None:
    with pytest.raises(ValueError, match="length"):
        StreakStrategy().validate_config({})
