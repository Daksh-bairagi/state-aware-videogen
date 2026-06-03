"""Prompt construction from structured shot metadata."""

from __future__ import annotations

from .state import Shot


DEFAULT_NEGATIVE_PROMPT = "blurry, distorted faces, unreadable text, inconsistent lighting, low quality"


def build_prompt(shot: Shot, global_style: str) -> str:
    """Build a stable generation prompt from one shot."""

    characters = ", ".join(shot["characters"]) if shot["characters"] else "none specified"
    continuity = shot["continuity"]
    return (
        f"{global_style}. {shot['description']}. "
        f"Characters: {characters}. "
        f"Location: {shot['location']}. "
        f"Continuity: previous context: {continuity['entry_context']}; "
        f"next context: {continuity['exit_context']}. "
        f"Duration: {shot['duration_sec']} seconds. "
        "Camera: cinematic, stable, coherent, smooth motion."
    )


def apply_prompts(shots: list[Shot], global_style: str) -> list[Shot]:
    """Return shots with prompt and negative prompt populated."""

    prompted: list[Shot] = []
    for shot in shots:
        updated = dict(shot)
        updated["visual_style"] = shot.get("visual_style") or global_style
        updated["prompt"] = build_prompt(updated, global_style)  # type: ignore[arg-type]
        updated["negative_prompt"] = shot.get("negative_prompt") or DEFAULT_NEGATIVE_PROMPT
        prompted.append(updated)  # type: ignore[arg-type]
    return prompted


def rewrite_prompt_for_edit(
    shot: Shot,
    user_edit: str,
    previous_shot: Shot | None = None,
    next_shot: Shot | None = None,
) -> str:
    """Rewrite a shot prompt with the user edit and neighboring continuity context."""

    neighbor_context: list[str] = []
    if previous_shot:
        neighbor_context.append(f"Previous shot: {previous_shot['description']}")
    if next_shot:
        neighbor_context.append(f"Next shot: {next_shot['description']}")

    continuity_text = " ".join(neighbor_context)
    return (
        f"{shot['prompt']} "
        f"Apply this user edit only where relevant: {user_edit}. "
        "Preserve the same characters, location, camera language, duration, and visual continuity. "
        f"{continuity_text}"
    ).strip()

