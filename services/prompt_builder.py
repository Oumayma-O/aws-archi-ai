"""Service for building structured prompts for architecture generation."""

from pathlib import Path


_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "architecture_prompt.md"


def _load_template() -> str:
    """Load the architecture prompt template from disk.

    Returns:
        The raw template string with a {system_description} placeholder.

    Raises:
        FileNotFoundError: If the template file does not exist.
    """
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def build_prompt(system_description: str) -> str:
    """Build a structured prompt requesting architecture JSON.

    Reads the prompt template from ``templates/architecture_prompt.md`` and
    inserts the user-provided system description verbatim.

    Args:
        system_description: Natural language description from the user.

    Returns:
        Complete prompt string for submission to Bedrock.
    """
    template = _load_template()
    return template.replace("{system_description}", system_description)
