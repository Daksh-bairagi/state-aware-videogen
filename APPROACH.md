# Technical Approach

## Gemini as Decision Maker

Gemini makes all the decisions. Shot planning, edit analysis, impact detection - it all goes through Gemini. We treat it as a decision maker that understands context and intent.

## LangGraph for Workflow

We use LangGraph because this is a stateful workflow with clear nodes, transitions, and retries. It fits the script → planning → generation → edit → regeneration flow better than plain functions.

It handles the flow from script → shot planning → generation → edit handling → regeneration, and keeps the state transitions clear.

## Shot Manifest as Source of Truth

Instead of just storing the final video, we store metadata for every shot - description, characters, location, asset paths. When a user edits, we:

1. Figure out which shots are affected
2. Regenerate only those
3. Recompose the video

This is the core idea. Without it, every edit regenerates everything.

## Regeneration Prompts with Constraints

When regenerating, we tell Gemini what to keep the same (characters, location, lighting, duration) and what to change. This keeps shots consistent.

## JSON Files for Storage

Simple storage. `projects/{project_id}/` with JSON files. Easy to inspect and debug.

## Streamlit for UI

Used Streamlit because time was low. It works, handles video preview and forms. That's enough.
