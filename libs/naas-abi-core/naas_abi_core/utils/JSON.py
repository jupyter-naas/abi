import json
import re

from naas_abi_core import logger


def _raw_decode_json_object(text: str) -> list | dict | None:
    """Parse the first JSON object or array in *text*, skipping any leading prose.

    Handles LLM output like: ``Some preamble.{ "key": "value" }`` where the
    opening brace is not on its own line and there are no markdown fences.
    """
    decoder = json.JSONDecoder()
    for opener in ("{", "["):
        start = 0
        while True:
            idx = text.find(opener, start)
            if idx == -1:
                break
            try:
                obj, _ = decoder.raw_decode(text, idx)
                return obj
            except json.JSONDecodeError:
                start = idx + 1
    return None


def extract_json_from_completion(completion_text: str) -> list | dict:
    """Extract JSON object from completion text that contains markdown formatting.

    Args:
        completion_text (str): Raw completion text containing JSON in markdown format

    Returns:
        dict: Parsed JSON object
    """
    # Find JSON content between ```json and ``` markers
    json_start = completion_text.find("```json\n")
    json_end = completion_text.rfind("```")

    if json_start == -1 or json_end == -1:
        # If no markdown markers found, try parsing the whole text
        json_str = completion_text
    else:
        # Extract content between markers and clean it
        json_start += len("```json\n")
        json_str = completion_text[json_start:json_end].strip()

    # Try multiple cleanup approaches
    attempts = [
        lambda x: x,  # Original string
        lambda x: x.replace("```", "").strip(),  # Remove markdown artifacts
        lambda x: x.replace("\n", "").replace(" ", ""),  # Remove all whitespace
        lambda x: x.replace("'", '"'),  # Replace single quotes with double quotes
        lambda x: re.sub(
            r"([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', x
        ),  # Quote unquoted keys
    ]

    for attempt in attempts:
        try:
            cleaned_str = attempt(json_str)
            return json.loads(cleaned_str)
        except json.JSONDecodeError as e:
            logger.debug(f"JSON parse attempt failed: {str(e)}")
            continue

    raw = _raw_decode_json_object(json_str)
    if raw is not None:
        return raw

    logger.error("Failed to parse JSON after all cleanup attempts")
    return {}
