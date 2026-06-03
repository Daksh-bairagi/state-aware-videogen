"""Incremental shot regeneration."""

from __future__ import annotations

from pathlib import Path

from .generator import generate_shot
from .prompt_builder import rewrite_prompt_for_edit
from .state import Shot


def regenerate_affected_shots(
    shots: list[Shot],
    affected_shot_ids: list[str],
    user_edit: str,
    project_id: str,
    base_dir: str | Path = ".",
) -> list[Shot]:
    """Regenerate only affected shots and preserve the rest."""

    affected = set(affected_shot_ids)
    ordered = sorted(shots, key=lambda shot: shot["order"])
    updated_shots: list[Shot] = []

    for index, shot in enumerate(ordered):
        updated = dict(shot)
        if shot["shot_id"] in affected:
            previous_shot = ordered[index - 1] if index > 0 else None
            next_shot = ordered[index + 1] if index < len(ordered) - 1 else None
            updated["version"] = shot["version"] + 1
            updated["status"] = "regenerating"
            updated["last_action"] = "regenerated"
            updated["prompt"] = rewrite_prompt_for_edit(shot, user_edit, previous_shot, next_shot)
            updated["asset_path"] = generate_shot(updated, project_id, base_dir)  # type: ignore[arg-type]
            if str(updated["asset_path"]).endswith(".mp4"):
                updated["status"] = "complete"
            else:
                updated["status"] = "failed"
                updated["last_action"] = "failed"
        else:
            updated["last_action"] = "preserved"
        updated_shots.append(updated)  # type: ignore[arg-type]

    return updated_shots
