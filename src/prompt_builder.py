"""Prompt construction from structured shot metadata.

This module keeps prompts consistent, explicit, and strongly constrained so the
LLM preserves shot identity while only changing the requested element.
"""

from __future__ import annotations

from .state import Shot


DEFAULT_NEGATIVE_PROMPT = "blurry, distorted faces, unreadable text, inconsistent lighting, low quality"


def format_shot_brief(shot: Shot) -> str:
    """Return a compact, LLM-friendly description of a shot."""

    characters = ", ".join(shot["characters"]) if shot["characters"] else "none"
    continuity = shot["continuity"]
    return (
        f"shot_id={shot['shot_id']}; scene_id={shot['scene_id']}; order={shot['order']}; "
        f"description={shot['description']}; characters={characters}; location={shot['location']}; "
        f"style={shot['visual_style']}; duration_sec={shot['duration_sec']}; "
        f"entry_context={continuity['entry_context']}; exit_context={continuity['exit_context']}"
    )


def build_prompt(shot: Shot, global_style: str) -> str:
    """Build a stable generation prompt from one shot.

    The prompt emphasizes a single coherent shot, continuity, and visual
    specificity so media generation has less room to drift.
    """

    characters = ", ".join(shot["characters"]) if shot["characters"] else "none specified"
    continuity = shot["continuity"]
    return (
        "Create one cinematic shot only. "
        f"Global style: {global_style}. "
        f"Primary action: {shot['description']}. "
        f"Characters: {characters}. "
        f"Location: {shot['location']}. "
        f"Continuity before this shot: {continuity['entry_context']}. "
        f"Continuity after this shot: {continuity['exit_context']}. "
        f"Duration: {shot['duration_sec']} seconds. "
        "Camera direction: keep a single continuous shot, with coherent framing, consistent lighting, "
        "clean subject identity, and no unrelated scene redesign. "
        "Prefer specific visual details over vague style words."
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
    """Rewrite a shot prompt with the user edit and neighboring continuity context.

    The rewritten prompt must preserve the original shot identity by explicitly
    listing immutable constraints extracted from the original shot metadata.
    Only the requested visual element is allowed to change.
    """

    # Extract immutable constraints FROM the original shot
    characters_list = ", ".join(shot["characters"]) if shot["characters"] else "none"
    
    immutable_section = (
        "IMMUTABLE (preserve exactly):\n"
        f"- Location: {shot['location']}\n"
        f"- Characters: {characters_list} (same identities, clothing, poses)\n"
        f"- Duration: {shot['duration_sec']} seconds\n"
        f"- Visual style: {shot['visual_style']}\n"
        f"- Shot structure: {shot['description']}\n"
        f"- Camera language: from original prompt\n"
        f"- Lighting: consistent with original mood\n"
        f"- Composition: same framing, same subject placement"
    )
    
    # Build the change section
    change_section = (
        f"CHANGE (minimal edit only):\n"
        f"- Apply this user edit: {user_edit}\n"
        f"- This is a localized adjustment, not a redesign\n"
        f"- Modify only what the edit requests\n"
        f"- Keep everything else visually identical to the original"
    )
    
    # Build continuity anchors
    continuity_lines = []
    if previous_shot:
        continuity_lines.append(f"Previous shot ends with: {previous_shot['description']}")
    if next_shot:
        continuity_lines.append(f"Next shot begins with: {next_shot['description']}")
    continuity_section = "\n".join(continuity_lines) if continuity_lines else "No adjacent shots specified"
    
    # Final prompt structure
    return (
        "You are REGENERATING an existing shot, not creating a new one.\n"
        f"Original generation prompt (reference only): {shot['prompt']}\n\n"
        f"{immutable_section}\n\n"
        f"{change_section}\n\n"
        f"CONTINUITY:\n{continuity_section}\n\n"
        "CRITICAL INSTRUCTION:\n"
        "Generate a version of the same shot with ONLY the requested edit applied. "
        "Do not redesign the composition, framing, camera angle, or visual mood. "
        "A side-by-side comparison with the original should show the shot nearly identical except for the specified change."
    ).strip()

