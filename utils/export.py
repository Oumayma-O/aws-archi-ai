"""File export and filename sanitization utilities."""

import re


def sanitize_filename(title: str) -> str:
    """
    Sanitize architecture title for use in filenames.

    Replaces spaces and special characters with underscores.
    Collapses consecutive underscores into a single underscore.
    Strips leading/trailing underscores.
    Returns 'untitled' as fallback for empty or whitespace-only titles.

    Args:
        title: Raw architecture title string.

    Returns:
        Sanitized filename-safe string containing only alphanumeric
        characters, underscores, and hyphens.
    """
    # Handle empty/whitespace-only titles with fallback
    if not title or not title.strip():
        return "untitled"

    # Replace any character that is not alphanumeric, underscore, or hyphen with underscore
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", title)

    # Collapse consecutive underscores into a single underscore
    sanitized = re.sub(r"_+", "_", sanitized)

    # Strip leading and trailing underscores
    sanitized = sanitized.strip("_")

    # If after sanitization the result is empty, use fallback
    if not sanitized:
        return "untitled"

    return sanitized


def generate_export_filename(title: str, format_name: str, extension: str) -> str:
    """
    Generate export filename in format: {sanitized_title}_{format}.{extension}

    Args:
        title: Architecture title.
        format_name: Export format identifier (e.g., "mermaid", "drawio").
        extension: File extension without dot.

    Returns:
        Complete filename string.
    """
    sanitized_title = sanitize_filename(title)
    return f"{sanitized_title}_{format_name}.{extension}"
