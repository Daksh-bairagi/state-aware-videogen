"""Workflow functions for initial generation and incremental edits.

The functions are intentionally usable without LangGraph installed. This keeps
the one-day MVP runnable while leaving a clean place to add a formal graph.
"""

from __future__ import annotations

from pathlib import Path

from .composer import compose_video
from .edit_analyzer import analyze_edit
from .generator import generate_shot
from .impact_analyzer import find_affected_shots
from .regenerator import regenerate_affected_shots
from .shot_planner import plan_shots
from .state import ProjectState, VideoGraphState, create_graph_state
from .storage import (
    create_project,
    load_project_state,
    load_shot_manifest,
    save_project_state,
    save_shot_manifest,
)


def create_project_from_script(
    script: str,
    global_style: str,
    base_dir: str | Path = ".",
    project_id: str | None = None,
) -> VideoGraphState:
    """Create a project and plan shots without generating media yet."""

    project_state = create_project(
        script=script,
        global_style=global_style,
        base_dir=base_dir,
        project_id=project_id,
    )
    shots = plan_shots(script, global_style)
    save_shot_manifest(project_state["project_id"], shots, base_dir)
    graph_state = create_graph_state(project_state, shots)
    graph_state["status"] = "planned"
    return graph_state


def generate_initial_video(project_id: str, base_dir: str | Path = ".") -> VideoGraphState:
    """Generate all missing shot assets and compose the first final video."""

    project_state = load_project_state(project_id, base_dir)
    shots = load_shot_manifest(project_id, base_dir)

    generated = []
    for shot in shots:
        updated = dict(shot)
        if not updated.get("asset_path"):
            updated["status"] = "generating"
            updated["asset_path"] = generate_shot(updated, project_id, base_dir)  # type: ignore[arg-type]
            if str(updated["asset_path"]).endswith(".mp4"):
                updated["status"] = "complete"
                updated["last_action"] = "generated"
            else:
                updated["status"] = "failed"
                updated["last_action"] = "failed"
        generated.append(updated)

    save_shot_manifest(project_id, generated, base_dir)  # type: ignore[arg-type]
    final_path = compose_video(project_state, generated, base_dir)  # type: ignore[arg-type]
    project_state["final_video_path"] = final_path
    save_project_state(project_state, base_dir)

    graph_state = create_graph_state(project_state, generated)  # type: ignore[arg-type]
    graph_state["final_video_path"] = final_path
    graph_state["status"] = "generated"
    return graph_state


def apply_user_edit(project_id: str, instruction: str, base_dir: str | Path = ".") -> VideoGraphState:
    """Apply a user edit by regenerating only affected shots."""

    project_state = load_project_state(project_id, base_dir)
    shots = load_shot_manifest(project_id, base_dir)

    edit_intent = analyze_edit(instruction)
    affected_shot_ids = find_affected_shots(edit_intent, shots)

    project_state["current_version"] += 1
    updated_shots = regenerate_affected_shots(
        shots=shots,
        affected_shot_ids=affected_shot_ids,
        user_edit=instruction,
        project_id=project_id,
        base_dir=base_dir,
    )
    save_shot_manifest(project_id, updated_shots, base_dir)

    final_path = compose_video(project_state, updated_shots, base_dir)
    project_state["final_video_path"] = final_path
    save_project_state(project_state, base_dir)

    graph_state = create_graph_state(project_state, updated_shots)
    graph_state["user_edit"] = instruction
    graph_state["edit_intent"] = edit_intent
    graph_state["affected_shot_ids"] = affected_shot_ids
    graph_state["final_video_path"] = final_path
    graph_state["status"] = "edited"
    return graph_state


def build_langgraph():
    """Build a LangGraph workflow when langgraph is installed.

    The direct functions above are the MVP execution path. This helper exists
    so the architecture can grow into explicit graph nodes without changing the
    rest of the app.
    """

    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return None

    from .state import VideoGraphState

    graph = StateGraph(VideoGraphState)
    graph.add_node("identity", lambda state: state)
    graph.set_entry_point("identity")
    graph.add_edge("identity", END)
    return graph.compile()


def summarize_regeneration(state: VideoGraphState) -> dict:
    """Return a compact summary for the UI."""

    affected = set(state.get("affected_shot_ids", []))
    return {
        "affected_shots": sorted(affected),
        "regenerated": [
            shot["shot_id"]
            for shot in state["shots"]
            if shot["shot_id"] in affected and shot["last_action"] == "regenerated"
        ],
        "preserved": [shot["shot_id"] for shot in state["shots"] if shot["last_action"] == "preserved"],
        "final_video_path": state.get("final_video_path"),
    }
