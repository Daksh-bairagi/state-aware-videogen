"""Final video composition from shot assets (LLM-generated only)."""

from __future__ import annotations

from pathlib import Path

from .state import ProjectState, Shot
from .storage import get_project_dir, save_project_state


def compose_video(
    project_state: ProjectState,
    shots: list[Shot],
    base_dir: str | Path = ".",
) -> str:
    """Compose ordered shot assets into a final video and return relative path."""

    project_dir = get_project_dir(project_state["project_id"], base_dir)
    final_dir = project_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    version = project_state["current_version"]
    filename = f"final_v{version}.mp4"
    output_path = final_dir / filename
    ordered = sorted(shots, key=lambda shot: shot["order"])
    asset_paths = [project_dir / shot["asset_path"] for shot in ordered if shot.get("asset_path")]

    import imageio.v2 as imageio

    writer = None
    appended_frames = 0
    try:
        writer = imageio.get_writer(str(output_path), fps=24, codec="libx264", macro_block_size=16)
        for asset_path in asset_paths:
            if asset_path.exists() and asset_path.suffix.lower() == ".mp4":
                reader = imageio.get_reader(str(asset_path))
                try:
                    for frame in reader:
                        writer.append_data(frame)
                        appended_frames += 1
                finally:
                    reader.close()
    finally:
        if writer is not None:
            writer.close()

    if appended_frames <= 0:
        raise RuntimeError(
            f"Composition failed: no real video shot assets available. "
            f"Asset paths: {asset_paths}"
        )

    project_state["final_video_path"] = f"final/{filename}"
    save_project_state(project_state, base_dir)
    return f"final/{filename}"
