"""Local JSON storage for projects and shot manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .state import ProjectState, Shot, create_project_state, touch_project_state


PROJECT_STATE_FILE = "project_state.json"
SHOT_MANIFEST_FILE = "shot_manifest.json"


def get_projects_root(base_dir: str | Path = ".") -> Path:
    """Return the local projects root."""

    return Path(base_dir).resolve() / "projects"


def get_project_dir(project_id: str, base_dir: str | Path = ".") -> Path:
    """Return the directory for one project."""

    return get_projects_root(base_dir) / project_id


def get_project_subdir(project_id: str, name: str, base_dir: str | Path = ".") -> Path:
    """Return a named project subdirectory."""

    return get_project_dir(project_id, base_dir) / name


def ensure_project_dirs(project_id: str, base_dir: str | Path = ".") -> Path:
    """Create the folder layout for a project and return the project directory."""

    project_dir = get_project_dir(project_id, base_dir)
    for dirname in ("shots", "final", "audio"):
        (project_dir / dirname).mkdir(parents=True, exist_ok=True)
    return project_dir


def write_json(path: str | Path, data: Any) -> None:
    """Write formatted JSON with stable UTF-8 encoding."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def read_json(path: str | Path) -> Any:
    """Read a JSON file."""

    return json.loads(Path(path).read_text(encoding="utf-8"))


def project_state_path(project_id: str, base_dir: str | Path = ".") -> Path:
    return get_project_dir(project_id, base_dir) / PROJECT_STATE_FILE


def shot_manifest_path(project_id: str, base_dir: str | Path = ".") -> Path:
    return get_project_dir(project_id, base_dir) / SHOT_MANIFEST_FILE


def save_project_state(project_state: ProjectState, base_dir: str | Path = ".") -> None:
    """Persist project-level state."""

    ensure_project_dirs(project_state["project_id"], base_dir)
    write_json(project_state_path(project_state["project_id"], base_dir), touch_project_state(project_state))


def load_project_state(project_id: str, base_dir: str | Path = ".") -> ProjectState:
    """Load project-level state."""

    return read_json(project_state_path(project_id, base_dir))


def save_shot_manifest(project_id: str, shots: list[Shot], base_dir: str | Path = ".") -> None:
    """Persist the shot manifest."""

    ensure_project_dirs(project_id, base_dir)
    write_json(shot_manifest_path(project_id, base_dir), shots)


def load_shot_manifest(project_id: str, base_dir: str | Path = ".") -> list[Shot]:
    """Load the shot manifest."""

    path = shot_manifest_path(project_id, base_dir)
    if not path.exists():
        return []
    return read_json(path)


def create_project(
    script: str,
    global_style: str,
    base_dir: str | Path = ".",
    project_id: str | None = None,
    locked_audio_path: str | None = None,
) -> ProjectState:
    """Create a persisted project with an empty shot manifest."""

    project_state = create_project_state(
        script=script,
        global_style=global_style,
        project_id=project_id,
        locked_audio_path=locked_audio_path,
    )
    ensure_project_dirs(project_state["project_id"], base_dir)
    save_project_state(project_state, base_dir)
    save_shot_manifest(project_state["project_id"], [], base_dir)
    return load_project_state(project_state["project_id"], base_dir)

