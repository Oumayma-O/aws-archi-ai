"""Input validation utilities for AWS Architect AI."""


def validate_input(description: str) -> bool:
    """
    Validate a system description input.

    Returns True if the input is valid (non-empty and not whitespace-only),
    False if the input should be rejected (empty or whitespace-only).

    Args:
        description: The user-provided system description string.

    Returns:
        True if valid, False if the input is empty or contains only whitespace.
    """
    if not description or not description.strip():
        return False
    return True
