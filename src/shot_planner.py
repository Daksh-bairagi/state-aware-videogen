"""Shot manifest planning via Gemini LLM only."""

from __future__ import annotations

from typing import Any

from .gemini_agent import ask_gemini_json
from .prompt_builder import apply_prompts
from .state import Shot


def make_shot_id(index: int) -> str:
    return f"shot_{index:03d}"


def plan_shots(script: str, global_style: str, min_shots: int = 3, max_shots: int = 6) -> list[Shot]:
    """Convert a script into a canonical shot manifest using LLM."""

    candidates = plan_shot_candidates_with_llm(script, global_style, min_shots, max_shots)
    if not candidates:
        raise RuntimeError(
            "Gemini shot planning failed. LLM is required; no deterministic fallback available."
        )

    shots: list[Shot] = []
    for index, candidate in enumerate(candidates, start=1):
        previous_text = candidates[index - 2]["description"] if index > 1 else "Start of video"
        next_text = candidates[index]["description"] if index < len(candidates) else "End of video"
        shot: Shot = {
            "shot_id": make_shot_id(index),
            "scene_id": candidate.get("scene_id", "scene_001"),
            "order": index,
            "script_text": candidate["script_text"],
            "description": candidate["description"],
            "characters": candidate.get("characters", []),
            "location": candidate.get("location", "unspecified location"),
            "visual_style": global_style,
            "duration_sec": int(candidate.get("duration_sec", 4)),
            "prompt": "",
            "negative_prompt": "",
            "asset_path": None,
            "version": 1,
            "status": "planned",
            "last_action": "planned",
            "continuity": {
                "entry_context": previous_text,
                "exit_context": next_text,
            },
        }
        shots.append(shot)

    return apply_prompts(shots, global_style)


def plan_shot_candidates_with_llm(
    script: str,
    global_style: str,
    min_shots: int,
    max_shots: int,
) -> list[dict[str, Any]]:
    """Ask Gemini for structured shot candidates."""

    system_prompt = (
        "You are a film shot-planning agent. Convert scripts into a concise shot list. "
        "Return JSON only. Do not include markdown."
    )
    user_prompt = (
        f"Script:\n{script}\n\n"
        f"Global visual style: {global_style}\n"
        f"Create between {min_shots} and {max_shots} shots.\n"
        "Return a JSON array. Each item must have: scene_id, order, script_text, "
        "description, characters, location, duration_sec. "
        "Descriptions must be visual and specific enough for image/video generation. "
        "characters must be an array of strings. duration_sec must be 4 to 8."
    )

    raw = ask_gemini_json(system_prompt, user_prompt)
    if not isinstance(raw, list):
        return []

    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(raw[:max_shots], start=1):
        if not isinstance(item, dict):
            continue
        script_text = str(item.get("script_text") or item.get("description") or "").strip()
        description = str(item.get("description") or script_text).strip()
        if not script_text or not description:
            continue
        characters = item.get("characters", [])
        if not isinstance(characters, list):
            characters = []
        try:
            duration_sec = int(item.get("duration_sec", 4))
        except (TypeError, ValueError):
            duration_sec = 4
        candidates.append(
            {
                "scene_id": str(item.get("scene_id") or "scene_001"),
                "order": index,
                "script_text": script_text,
                "description": description,
                "characters": [str(character) for character in characters[:4]],
                "location": str(item.get("location") or "unspecified location"),
                "duration_sec": max(4, min(duration_sec, 8)),
            }
        )

    if len(candidates) < min_shots:
        return []
    return candidates
