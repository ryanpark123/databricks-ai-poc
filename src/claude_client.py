"""
Shared Claude API client for the Databricks POC agents.

In Databricks, pass the API key in via a secret:
    api_key = dbutils.secrets.get(scope="claude-poc", key="anthropic_api_key")

Locally, it falls back to the ANTHROPIC_API_KEY environment variable.
"""

import os
from anthropic import Anthropic


def get_client(api_key: str | None = None) -> Anthropic:
    """Return an initialized Anthropic client.

    Args:
        api_key: explicit key (e.g. pulled from Databricks secrets). If None,
                  falls back to the ANTHROPIC_API_KEY env var.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError(
            "No Anthropic API key found. Pass one explicitly, set ANTHROPIC_API_KEY, "
            "or pull from Databricks secrets with dbutils.secrets.get(...)."
        )
    return Anthropic(api_key=key)


def ask_claude(client: Anthropic, system: str, user_prompt: str, model: str = "claude-sonnet-4-6") -> str:
    """Single-turn helper: send a system prompt + user prompt, get back text."""
    response = client.messages.create(
        model=model,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")
