"""LangGraph workflow for state-aware video generation."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from langgraph.graph import END, StateGraph

from .composer import compose_video
from .edit_analyzer import analyze_edit
from .generator import generate_shot
from .impact_analyzer import find_affected_shots
from .regenerator import regenerate_affected_shots
from .shot_planner import plan_shots
from .state import VideoGraphState, create_graph_state
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
    """Create a project and stop after shot planning."""

    project = create_project(script, global_style, base_dir, project_id)
    state = create_graph_state(project)
    state["status"] = "plan_only"
    return build_langgraph(base_dir).invoke(state)


def generate_initial_video(project_id: str, base_dir: str | Path = ".") -> VideoGraphState:
    """Generate shot assets and compose the first video."""

    state = load_graph_state(project_id, base_dir)
    state["status"] = "initial_generate"
    return build_langgraph(base_dir).invoke(state)


def apply_user_edit(project_id: str, instruction: str, base_dir: str | Path = ".") -> VideoGraphState:
    """Apply one edit by regenerating only affected shots."""

    state = load_graph_state(project_id, base_dir)
    state["status"] = "edit"
    state["user_edit"] = instruction
    return build_langgraph(base_dir).invoke(state)


def build_langgraph(base_dir: str | Path = "."):
    """Build the full lifecycle graph."""

    graph = StateGraph(VideoGraphState)

    graph.add_node("route_request", lambda state: state)
    graph.add_node("plan_shots", bind_base_dir(plan_shots_node, base_dir))
    graph.add_node("generate_shots", bind_base_dir(generate_shots_node, base_dir))
    graph.add_node("compose_generated_video", bind_base_dir(compose_generated_video_node, base_dir))
    graph.add_node("analyze_edit", analyze_edit_node)
    graph.add_node("find_affected_shots", find_affected_shots_node)
    graph.add_node("bump_project_version", bind_base_dir(bump_project_version_node, base_dir))
    graph.add_node("regenerate_shots", bind_base_dir(regenerate_shots_node, base_dir))
    graph.add_node("compose_edited_video", bind_base_dir(compose_edited_video_node, base_dir))

    graph.set_entry_point("route_request")
    graph.add_conditional_edges(
        "route_request",
        route_request,
        {
            "plan": "plan_shots",
            "generate": "generate_shots",
            "edit": "analyze_edit",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "plan_shots",
        route_after_planning,
        {
            "generate": "generate_shots",
            "end": END,
        },
    )
    graph.add_edge("generate_shots", "compose_generated_video")
    graph.add_edge("compose_generated_video", END)
    graph.add_edge("analyze_edit", "find_affected_shots")
    graph.add_edge("find_affected_shots", "bump_project_version")
    graph.add_edge("bump_project_version", "regenerate_shots")
    graph.add_edge("regenerate_shots", "compose_edited_video")
    graph.add_edge("compose_edited_video", END)

    return graph.compile()


def load_graph_state(project_id: str, base_dir: str | Path = ".") -> VideoGraphState:
    """Load project JSON files into graph state."""

    project = load_project_state(project_id, base_dir)
    shots = load_shot_manifest(project_id, base_dir)
    return create_graph_state(project, shots)


def route_request(state: VideoGraphState) -> str:
    """Route new projects, generation requests, and edits."""

    if state.get("user_edit") or state["status"] == "edit":
        return "edit"
    if state["status"] == "plan_only":
        return "plan"
    if state["status"] == "initial_generate":
        return "generate" if state["shots"] else "plan"
    if any(not shot.get("asset_path") for shot in state["shots"]):
        return "generate"
    return "end"


def route_after_planning(state: VideoGraphState) -> str:
    """Stop for plan-only requests, otherwise continue to generation."""

    return "end" if state["status"] == "planned" else "generate"


def bind_base_dir(
    node: Callable[[VideoGraphState, str | Path], VideoGraphState],
    base_dir: str | Path,
) -> Callable[[VideoGraphState], VideoGraphState]:
    """Attach the project root to a graph node."""

    return lambda state: node(state, base_dir)


def plan_shots_node(state: VideoGraphState, base_dir: str | Path = ".") -> VideoGraphState:
    """Plan shots from the script."""

    status = state["status"]
    shots = plan_shots(state["script"], state["global_style"])
    save_shot_manifest(state["project_id"], shots, base_dir)

    updated = dict(state)
    updated["shots"] = shots
    updated["status"] = "planned" if status == "plan_only" else "planned_for_generation"
    return updated  # type: ignore[return-value]


def generate_shots_node(state: VideoGraphState, base_dir: str | Path = ".") -> VideoGraphState:
    """Generate missing shot MP4 files."""

    shots = []
    for shot in state["shots"]:
        updated = dict(shot)
        if not updated.get("asset_path"):
            updated["status"] = "generating"
            updated["asset_path"] = generate_shot(updated, state["project_id"], base_dir)  # type: ignore[arg-type]
            updated["status"] = "complete"
            updated["last_action"] = "generated"
        shots.append(updated)

    save_shot_manifest(state["project_id"], shots, base_dir)  # type: ignore[arg-type]
    updated_state = dict(state)
    updated_state["shots"] = shots
    updated_state["status"] = "shots_generated"
    return updated_state  # type: ignore[return-value]


def compose_generated_video_node(state: VideoGraphState, base_dir: str | Path = ".") -> VideoGraphState:
    """Compose the initial final video."""

    return compose_video_node(state, base_dir, "generated")


def analyze_edit_node(state: VideoGraphState) -> VideoGraphState:
    """Turn the edit instruction into structured intent."""

    if not state.get("user_edit"):
        raise ValueError("Cannot analyze edit: user_edit is missing.")

    updated = dict(state)
    updated["edit_intent"] = analyze_edit(state["user_edit"])
    updated["status"] = "edit_analyzed"
    return updated  # type: ignore[return-value]


def find_affected_shots_node(state: VideoGraphState) -> VideoGraphState:
    """Select the shots that need regeneration."""

    if state["edit_intent"] is None:
        raise ValueError("Cannot find affected shots: edit_intent is missing.")

    updated = dict(state)
    updated["affected_shot_ids"] = find_affected_shots(state["edit_intent"], state["shots"])
    updated["status"] = "impact_analyzed"
    return updated  # type: ignore[return-value]


def bump_project_version_node(state: VideoGraphState, base_dir: str | Path = ".") -> VideoGraphState:
    """Advance the project version before regeneration."""

    project = load_project_state(state["project_id"], base_dir)
    project["current_version"] += 1
    save_project_state(project, base_dir)

    updated = dict(state)
    updated["current_version"] = project["current_version"]
    updated["status"] = "version_incremented"
    return updated  # type: ignore[return-value]


def regenerate_shots_node(state: VideoGraphState, base_dir: str | Path = ".") -> VideoGraphState:
    """Regenerate affected shots and preserve the rest."""

    if not state.get("user_edit"):
        raise ValueError("Cannot regenerate shots: user_edit is missing.")

    shots = regenerate_affected_shots(
        shots=state["shots"],
        affected_shot_ids=state["affected_shot_ids"],
        user_edit=state["user_edit"],
        project_id=state["project_id"],
        base_dir=base_dir,
    )
    save_shot_manifest(state["project_id"], shots, base_dir)

    updated = dict(state)
    updated["shots"] = shots
    updated["status"] = "shots_regenerated"
    return updated  # type: ignore[return-value]


def compose_edited_video_node(state: VideoGraphState, base_dir: str | Path = ".") -> VideoGraphState:
    """Compose the edited final video."""

    return compose_video_node(state, base_dir, "edited")


def compose_video_node(
    state: VideoGraphState,
    base_dir: str | Path = ".",
    final_status: str = "generated",
) -> VideoGraphState:
    """Compose current shots and persist the final video path."""

    project = load_project_state(state["project_id"], base_dir)
    final_path = compose_video(project, state["shots"], base_dir)
    project["final_video_path"] = final_path
    save_project_state(project, base_dir)

    updated = dict(state)
    updated["current_version"] = project["current_version"]
    updated["final_video_path"] = final_path
    updated["status"] = final_status
    return updated  # type: ignore[return-value]


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
