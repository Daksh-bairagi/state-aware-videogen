"""User edit understanding via Gemini LLM only."""

from __future__ import annotations

from typing import Any

from .gemini_agent import ask_gemini_json


def analyze_edit(instruction: str) -> dict[str, Any]:
    """Convert a natural-language edit into structured intent using LLM."""

    llm_intent = analyze_edit_with_llm(instruction)
    if not llm_intent:
        raise RuntimeError(
            "Edit analysis failed. LLM is required; no deterministic fallback available."
        )
    return llm_intent


def analyze_edit_with_llm(instruction: str) -> dict[str, Any] | None:
    """Ask Gemini to structure the edit instruction."""

    system_prompt = (
        "You are an edit-intent extraction agent for an incremental video editor. "
        "Return JSON only. Do not include markdown."
    )
    user_prompt = (
        f"Edit instruction: {instruction}\n\n"
        "Return a JSON object with: raw_instruction, edit_type, target_objects, "
        "target_characters, target_location, style_change, requires_global_change, keywords. "
        "edit_type should be one of localized_change, visual_object_change, character_change, "
        "location_change, global_style_change. Arrays must contain strings."
    )
    raw = ask_gemini_json(system_prompt, user_prompt)
    if not isinstance(raw, dict):
        return None

    edit_type = str(raw.get("edit_type") or "localized_change")
    if edit_type not in {
        "localized_change",
        "visual_object_change",
        "character_change",
        "location_change",
        "global_style_change",
    }:
        edit_type = "localized_change"

    return {
        "raw_instruction": instruction,
        "edit_type": edit_type,
        "target_objects": normalize_string_list(raw.get("target_objects")),
        "target_characters": normalize_string_list(raw.get("target_characters")),
        "target_location": normalize_optional_string(raw.get("target_location")),
        "style_change": normalize_optional_string(raw.get("style_change")),
        "requires_global_change": bool(raw.get("requires_global_change")),
        "keywords": normalize_string_list(raw.get("keywords")),
    }


def normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip().lower() for item in value if str(item).strip()]


def normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None



