"""Tests for the calculator module."""

from calculator import add, subtract


def test_add_positive() -> None:
    assert add(2, 3) == 5


def test_add_negative() -> None:
    assert add(-1, -2) == -3


def test_add_zero() -> None:
    assert add(0, 0) == 0


def test_subtract_basic() -> None:
    assert subtract(5, 3) == 2


def test_subtract_negative_result() -> None:
    assert subtract(3, 5) == -2
