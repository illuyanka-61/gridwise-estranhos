"""Parser for LLM structured output into Pydantic models."""

import json
import re
from typing import Any

from app.schemas.directives import DirectiveInterpretationItem


class LLMParseError(Exception):
    """Raised when LLM output cannot be parsed into the expected directive schema."""

    pass


def extract_json_string(text: str) -> str:
    """Extracts raw JSON string from potentially fenced or verbose text."""
    clean = text.strip()

    # Look for markdown code block ```json ... ```
    m = re.search(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", clean, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Look for bracketed array or object
    m_array = re.search(r"(\[.*\])", clean, re.DOTALL)
    if m_array:
        return m_array.group(1).strip()

    m_obj = re.search(r"(\{.*\})", clean, re.DOTALL)
    if m_obj:
        return m_obj.group(1).strip()

    return clean


def parse_llm_output(raw_text: str) -> list[DirectiveInterpretationItem]:
    """
    Parses LLM response string into a list of validated DirectiveInterpretationItem objects.
    """
    json_str = extract_json_string(raw_text)
    try:
        data: Any = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise LLMParseError(f"Failed to decode LLM response as JSON: {exc}\nRaw: {raw_text[:200]}") from exc

    # If LLM wrapped array in a dictionary (e.g. {"directives": [...]})
    if isinstance(data, dict):
        for k in ("directives", "directive_interpretation", "interpretations", "items", "results"):
            if k in data and isinstance(data[k], list):
                data = data[k]
                break

    if not isinstance(data, list):
        raise LLMParseError(f"Expected a JSON array of directive interpretations, got {type(data)}")

    results: list[DirectiveInterpretationItem] = []
    for i, item in enumerate(data):
        try:
            parsed_item = DirectiveInterpretationItem.model_validate(item)
            results.append(parsed_item)
        except Exception as exc:
            raise LLMParseError(f"Validation failed for interpretation item {i}: {exc}") from exc

    return results
