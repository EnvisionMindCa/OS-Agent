from __future__ import annotations

__all__: list[str] = ["add_two_numbers"]


def add_two_numbers(a: int, b: int) -> int:  # noqa: D401
    """Add two numbers together.

    Args:
        a (int): First number to add.
        b (int): Second number to add.

    Returns:
        int: The sum of the two numbers.
    """
    return a + b