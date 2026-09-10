import json
import re

from worker.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def call_claude(system: str, user: str, max_tokens: int = 4096) -> str:
    client = _get_client()
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def extract_json(text: str):
    """Claude sometimes wraps JSON in prose or a ```json fence; pull the payload out."""
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = fence_match.group(1) if fence_match else text

    starts = [i for i in (candidate.find("["), candidate.find("{")) if i != -1]
    start = min(starts) if starts else 0
    return json.loads(candidate[start:])
