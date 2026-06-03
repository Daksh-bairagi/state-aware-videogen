"""Determine which shots are affected by a user edit."""

from __future__ import annotations

from .gemini_agent import ask_gemini_json
from .state import Shot


def find_affected_shots(edit_intent: dict, shots: list[Shot]) -> list[str]:
    """Return shot IDs that should be regenerated using LLM analysis."""

    if not shots:
        return []

    if edit_intent.get("requires_global_change"):
        return [shot["shot_id"] for shot in shots]

    llm_affected = find_affected_shots_with_llm(edit_intent, shots)
    if not llm_affected:
        raise RuntimeError(
            "Impact analysis failed. LLM is required; no deterministic fallback available."
        )
    return llm_affected


def find_affected_shots_with_llm(edit_intent: dict, shots: list[Shot]) -> list[str]:
    """Ask Gemini which existing shots should be regenerated."""

    shot_summaries = [
        {
            "shot_id": shot["shot_id"],
            "order": shot["order"],
            "description": shot["description"],
            "characters": shot["characters"],
            "location": shot["location"],
            "script_text": shot["script_text"],
        }
        for shot in shots
    ]
    system_prompt = (
        "You are an impact-analysis agent for an incremental video editor. "
        "Choose only the shots directly affected by the edit. Return JSON only."
    )
    user_prompt = (
        f"Edit intent: {edit_intent}\n\n"
        f"Shots: {shot_summaries}\n\n"
        "Return a JSON object with one field: affected_shot_ids, an array of shot_id strings. "
        "Do not include preserved shots unless they must visually change."
    )
    raw = ask_gemini_json(system_prompt, user_prompt)
    if not isinstance(raw, dict):
        return []
    valid_ids = {shot["shot_id"] for shot in shots}
    affected = [
        str(shot_id)
        for shot_id in raw.get("affected_shot_ids", [])
        if str(shot_id) in valid_ids
    ]
    return affected



