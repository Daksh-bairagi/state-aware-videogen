"""LangChain-backed Gemini agent helpers."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path


DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_KEY_PLACEHOLDER = "your_gemini_api_key_here"
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def load_project_env() -> None:
    """Load project .env values without overwriting existing environment."""

    try:
        from dotenv import load_dotenv

        load_dotenv(ENV_PATH)
        return
    except Exception:
        pass

    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def get_gemini_api_key() -> str | None:
    """Load and return the Gemini API key from the local environment."""

    load_project_env()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == GEMINI_API_KEY_PLACEHOLDER:
        return None
    return api_key


@lru_cache(maxsize=1)
def get_gemini_agent():
    """Create the Gemini chat model through LangChain when configured."""

    api_key = get_gemini_api_key()
    if not api_key:
        return None

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except Exception:
        return None

    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        google_api_key=api_key,
        temperature=0.3,
    )


@lru_cache(maxsize=1)
def get_genai_client():
    """Create the Google GenAI media client when configured."""

    api_key = get_gemini_api_key()
    if not api_key:
        return None

    try:
        from google import genai
    except Exception:
        return None

    return genai.Client(api_key=api_key)


def ask_gemini_agent(system_prompt: str, user_prompt: str) -> str | None:
    """Call Gemini and return text content if available.

    LangChain is used when installed. The direct SDK fallback keeps the app from
    silently becoming deterministic-only in environments where dependencies
    have not been refreshed yet.
    """

    agent = get_gemini_agent()
    if agent is not None:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            response = agent.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            return normalize_content(getattr(response, "content", None))
        except Exception:
            pass

    client = get_genai_client()
    if client is None:
        return None

    try:
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
            contents=f"{system_prompt}\n\n{user_prompt}",
        )
        return normalize_content(getattr(response, "text", None))
    except Exception:
        return None


def normalize_content(content) -> str | None:
    """Normalize Gemini/LangChain response content into plain text."""

    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, list):
        return "\n".join(str(part) for part in content).strip() or None
    return None


def ask_gemini_json(system_prompt: str, user_prompt: str) -> dict | list | None:
    """Call Gemini and parse a JSON object or array from the response."""

    text = ask_gemini_agent(system_prompt, user_prompt)
    if not text:
        return None

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start_indexes = [index for index in (cleaned.find("{"), cleaned.find("[")) if index >= 0]
        if not start_indexes:
            return None
        start = min(start_indexes)
        end = max(cleaned.rfind("}"), cleaned.rfind("]"))
        if end <= start:
            return None
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
