"""Core state models for the incremental video generator.

The shot manifest is the domain source of truth. These types keep the
manifest explicit and easy to validate before generation or regeneration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, NotRequired, TypedDict
from uuid import uuid4


ShotStatus = Literal["planned", "generating", "complete", "failed", "regenerating"]
ShotAction = Literal["planned", "generated", "preserved", "regenerated", "failed"]


class Continuity(TypedDict):
    entry_context: str
    exit_context: str


class Shot(TypedDict):
    shot_id: str
    scene_id: str
    order: int
    script_text: str
    description: str
    characters: list[str]
    location: str
    visual_style: str
    duration_sec: int
    prompt: str
    negative_prompt: str
    asset_path: str | None
    version: int
    status: ShotStatus
    last_action: ShotAction
    continuity: Continuity


class ProjectState(TypedDict):
    project_id: str
    script: str
    global_style: str
    current_version: int
    locked_audio_path: str | None
    final_video_path: str | None
    created_at: str
    updated_at: str


class VideoGraphState(TypedDict):
    project_id: str
    script: str
    global_style: str
    scenes: list[dict[str, Any]]
    shots: list[Shot]
    user_edit: str | None
    edit_intent: dict[str, Any] | None
    affected_shot_ids: list[str]
    locked_audio_path: str | None
    final_video_path: str | None
    current_version: int
    status: str
    error: NotRequired[str]


def utc_now_iso() -> str:
    """Return a stable UTC timestamp for persisted project state."""

    return datetime.now(timezone.utc).isoformat()


def new_project_id(prefix: str = "project") -> str:
    """Create a short unique project id suitable for folder names."""

    return f"{prefix}_{uuid4().hex[:8]}"


def create_project_state(
    script: str,
    global_style: str,
    project_id: str | None = None,
    locked_audio_path: str | None = None,
) -> ProjectState:
    """Create the initial persisted project state."""

    now = utc_now_iso()
    return {
        "project_id": project_id or new_project_id(),
        "script": script,
        "global_style": global_style,
        "current_version": 1,
        "locked_audio_path": locked_audio_path,
        "final_video_path": None,
        "created_at": now,
        "updated_at": now,
    }


def create_graph_state(project_state: ProjectState, shots: list[Shot] | None = None) -> VideoGraphState:
    """Create the initial in-memory graph state from persisted project state."""

    return {
        "project_id": project_state["project_id"],
        "script": project_state["script"],
        "global_style": project_state["global_style"],
        "scenes": [],
        "shots": shots or [],
        "user_edit": None,
        "edit_intent": None,
        "affected_shot_ids": [],
        "locked_audio_path": project_state["locked_audio_path"],
        "final_video_path": project_state["final_video_path"],
        "current_version": project_state["current_version"],
        "status": "created",
    }


def touch_project_state(project_state: ProjectState) -> ProjectState:
    """Return project state with an updated timestamp."""

    updated = dict(project_state)
    updated["updated_at"] = utc_now_iso()
    return updated  # type: ignore[return-value]

