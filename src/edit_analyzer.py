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
    """Ask Gemini to structure the edit instruction.

    The prompt requests a conservative, machine-readable edit intent so the
    impact analyzer can select only the shots that must change.
    """

    system_prompt = (
        "You are an edit-intent extraction agent for an incremental video editor. "
        "Your job is to identify the smallest visual change scope possible. "
        "Be conservative: only mark a global change when the instruction clearly "
        "affects the whole video. Return JSON only. Do not include markdown."
    )
    user_prompt = (
        f"Edit instruction: {instruction}\n\n"
        "Return a JSON object with these keys: raw_instruction, edit_type, scope, "
        "target_objects, target_characters, target_location, style_change, "
        "requires_global_change, keywords, confidence, rationale.\n"
        "Use these edit_type values only: localized_change, visual_object_change, "
        "character_change, location_change, global_style_change.\n"
        "Use these scope values only: local, regional, global.\n"
        "Rules:\n"
        "- target_objects, target_characters, and keywords must be arrays of strings\n"
        "- requires_global_change should be true only when the edit affects every shot or the overall style\n"
        "- confidence should be a number from 0 to 1\n"
        "- rationale should be short, factual, and explain which visual elements are affected\n"
        "- prefer the smallest valid scope when the edit is ambiguous"
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
        "scope": normalize_optional_string(raw.get("scope")) or ("global" if bool(raw.get("requires_global_change")) else "local"),
        "target_objects": normalize_string_list(raw.get("target_objects")),
        "target_characters": normalize_string_list(raw.get("target_characters")),
        "target_location": normalize_optional_string(raw.get("target_location")),
        "style_change": normalize_optional_string(raw.get("style_change")),
        "requires_global_change": bool(raw.get("requires_global_change")),
        "keywords": normalize_string_list(raw.get("keywords")),
        "confidence": raw.get("confidence"),
        "rationale": normalize_optional_string(raw.get("rationale")),
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



