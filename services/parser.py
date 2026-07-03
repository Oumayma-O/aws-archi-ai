"""Response parser service for extracting and validating LLM output.

With the Converse API + Tool Calling, the response is already structured JSON
from the toolUse block. The extract_json function is kept as a safety net for
edge cases where the response might include surrounding text.
"""

import json

from pydantic import ValidationError

from models.architecture import ArchitectureModel
from services.exceptions import JsonExtractionError


def extract_json(response_text: str) -> str:
    """Extract JSON from the response text.

    Handles common LLM output patterns:
    - Clean JSON (from Converse API tool calling)
    - JSON wrapped in markdown code fences (```json ... ```)
    - JSON with surrounding text

    Args:
        response_text: Raw text from LLM response.

    Returns:
        JSON string extracted from the response.

    Raises:
        JsonExtractionError: If no complete JSON object is found.
    """
    import re

    # Strip markdown code fences if present
    cleaned = response_text.strip()
    # Remove ```json ... ``` or ``` ... ```
    fence_pattern = re.compile(r'^```(?:json)?\s*\n?(.*?)\n?```\s*$', re.DOTALL)
    fence_match = fence_pattern.match(cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # First, try direct JSON parse (expected path)
    try:
        json.loads(cleaned)
        return cleaned
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: extract by brace matching
    start_index = cleaned.find("{")
    if start_index == -1:
        raise JsonExtractionError(
            "No JSON object found in response: no opening brace detected."
        )

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start_index, len(cleaned)):
        char = cleaned[i]

        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            if in_string:
                escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                extracted = cleaned[start_index : i + 1]
                # Validate it's actual JSON
                try:
                    json.loads(extracted)
                    return extracted
                except (json.JSONDecodeError, ValueError):
                    # Continue looking for a valid JSON object
                    continue

    raise JsonExtractionError(
        "No complete JSON object found in response: unmatched braces."
    )


def parse_architecture(json_str: str) -> ArchitectureModel:
    """Parse and validate JSON string against the Architecture model.

    Args:
        json_str: Raw JSON string to parse.

    Returns:
        Validated ArchitectureModel instance.

    Raises:
        ValidationError: If JSON doesn't conform to schema.
    """
    data = json.loads(json_str)
    return ArchitectureModel.model_validate(data)
