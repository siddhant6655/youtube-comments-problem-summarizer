import json


def parse_json(text: str):
    """Parse a JSON object/array out of a Claude text response, tolerating ```json fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)
