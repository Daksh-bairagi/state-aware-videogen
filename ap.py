"""Streamlit demo for the state-aware incremental video generator (copy).

This file mirrors `app.py` to provide an alternate entrypoint for Streamlit
that forces a fresh module import when the original app was cached.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

import streamlit as st

from src.graph import (
    apply_user_edit,
    create_project_from_script,
    generate_initial_video,
    summarize_regeneration,
)
from src.storage import get_project_dir, load_project_state, load_shot_manifest


DEFAULT_SCRIPT = (
    "A detective enters an old archive room. "
    "Dust floats in the air as she walks between shelves. "
    "She finds a glowing blue file on a wooden desk. "
    "Suddenly the lights flicker and go out."
)


def main() -> None:
    st.set_page_config(page_title="StateAware Video Generator (alt)", layout="wide")
    st.title("StateAware Incremental Video Generator (alt)")
    st.markdown(f"**AP UI loaded at {datetime.utcnow().isoformat()} UTC**")

    if "project_id" not in st.session_state:
        st.session_state.project_id = None
    if "last_summary" not in st.session_state:
        st.session_state.last_summary = None

    left, right = st.columns([0.38, 0.62])

    with left:
        st.subheader("Script")
        script = st.text_area("Script", value=DEFAULT_SCRIPT, height=180, label_visibility="collapsed")
        global_style = st.text_input("Global style", value="cinematic noir, moody lighting")

        if st.button("Create Shot Plan", use_container_width=True):
            try:
                state = create_project_from_script(script, global_style)
                st.session_state.project_id = state["project_id"]
                st.session_state.last_summary = None
                st.success(f"Created {state['project_id']}")
            except Exception as exc:
                st.error(str(exc))

        if st.session_state.project_id and st.button("Generate Initial Video", use_container_width=True):
            try:
                state = generate_initial_video(st.session_state.project_id)
                st.session_state.last_summary = summarize_regeneration(state)
                st.success("Initial video generated")
            except Exception as exc:
                st.error(str(exc))

        st.subheader("User Edit")
        instruction = st.text_input("Edit instruction", value="Make the glowing file red instead of blue.")
        if st.session_state.project_id and st.button("Apply Edit", use_container_width=True):
            try:
                state = apply_user_edit(st.session_state.project_id, instruction)
                st.session_state.last_summary = summarize_regeneration(state)
                st.success("Edit applied")
            except Exception as exc:
                st.error(str(exc))

    with right:
        render_project_preview(st.session_state.project_id)
        if st.session_state.last_summary:
            st.subheader("Regeneration Summary")
            st.json(st.session_state.last_summary)


def render_project_preview(project_id: str | None) -> None:
    if not project_id:
        st.info("Create a shot plan to begin.")
        return

    project_state = load_project_state(project_id)
    shots = load_shot_manifest(project_id)
    project_dir = get_project_dir(project_id)

    st.subheader("Video Preview")
    final_video_path = project_state.get("final_video_path")
    if final_video_path:
        video_path = project_dir / final_video_path
        if video_path.exists() and video_path.suffix.lower() == ".mp4":
            st.video(str(video_path))
        else:
            st.caption(f"Preview artifact: {video_path}")
    else:
        st.caption("No final video generated yet.")

    st.subheader("Shot Timeline")
    if shots:
        st.dataframe(
            [
                {
                    "shot_id": shot["shot_id"],
                    "order": shot["order"],
                    "description": shot["description"],
                    "version": shot["version"],
                    "status": shot["status"],
                    "last_action": shot["last_action"],
                    "asset_path": shot["asset_path"],
                }
                for shot in shots
            ],
            use_container_width=True,
        )

        st.subheader("Generated Shot Assets")
        for shot in shots:
            asset_path = shot.get("asset_path")
            if not asset_path:
                continue
            full_path = project_dir / asset_path
            with st.expander(f"{shot['shot_id']} v{shot['version']} - {shot['last_action']}"):
                st.write(shot["description"])
                if full_path.exists() and full_path.suffix.lower() == ".mp4":
                    st.video(str(full_path))
                else:
                    st.caption(str(full_path))


if __name__ == "__main__":
    main()
