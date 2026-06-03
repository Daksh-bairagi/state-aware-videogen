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
    """Ask Gemini which existing shots should be regenerated.

    The prompt asks for conservative, score-based impact reasoning so only
    directly affected shots are selected.
    """

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
        "Select only shots that must change because the edit is visually present in them. "
        "Be conservative and prefer leaving a shot untouched when the effect is indirect or uncertain. "
        "Return JSON only. No markdown, no extra text."
    )
    user_prompt = (
        f"Edit intent: {edit_intent}\n\n"
        f"Shots: {shot_summaries}\n\n"
        "Return a JSON object with two fields: affected_shot_ids and scored_impacts.\n"
        "affected_shot_ids must be an array of shot_id strings that must change.\n"
        "scored_impacts must be an array of objects with shot_id, impact_score, and reason.\n"
        "Use impact_score from 0 to 1, where 1 means the shot must be regenerated.\n"
        "Include only shots that are directly or clearly visually impacted.\n"
        "If a shot is only loosely related, give it a low score and exclude it from affected_shot_ids.\n"
        "Do not include preserved shots unless their visible content truly changes."
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



