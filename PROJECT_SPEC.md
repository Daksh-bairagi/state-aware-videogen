# Dynamic Script-To-Video Feedback Loop

## 1. Objective

Build a state-aware incremental video generator that:

1. Takes a user script.
2. Breaks the script into scenes and shots.
3. Generates a video as multiple shot-level assets.
4. Allows the user to give an edit instruction.
5. Detects which shots are affected by the edit.
6. Regenerates only the affected shots.
7. Preserves unchanged shots and background music.
8. Re-composes the final video.

Core demo statement:

> Instead of regenerating the whole video after feedback, the system tracks video state at the shot level and regenerates only the affected parts.

The priority is a working one-day MVP. The architecture should be simple, explainable, and technically strong enough for hackathons, interviews, and resume discussion.

---

## 2. Core Innovation

The core innovation is the **shot manifest**.

The final video is not the source of truth. The source of truth is:

```text
script -> shot_manifest -> generated shot assets -> final video
```

Each shot stores:

- The script text it represents
- The generation prompt
- Characters, location, and visual style
- Duration
- Generated asset path
- Version number
- Continuity metadata
- Whether it was preserved or regenerated

This makes partial regeneration possible.

Interview talking point:

> The generated video is an output artifact. The shot manifest is the editable state that allows localized regeneration.

---

## 3. MVP Architecture

```text
Streamlit UI
   |
   v
LangGraph Workflow
   |
   +--> Script Parser
   +--> Shot Planner
   +--> Prompt Builder
   +--> Shot Generator
   +--> Video Composer
   +--> Edit Analyzer
   +--> Impact Analyzer
   +--> Prompt Rewriter
   +--> Shot Regenerator
   +--> Recomposer
   |
   v
Local Project Storage
   |
   +--> project_state.json
   +--> shot_manifest.json
   +--> shot videos/images
   +--> final video
```

Use:

- **Streamlit** for the UI
- **LangGraph** for stateful workflow orchestration
- **Gemini models** for script breakdown, edit understanding, and media generation where available
- **MoviePy or FFmpeg** for video composition
- **Local JSON files** for project state
- **Gemini-based video/image generation first**, placeholder generation as a fallback

Senior engineering principle:

> LangGraph controls the workflow. The shot manifest owns the video state.

---

## 4. System Components

### 4.1 Streamlit UI

Purpose:

Provide a simple demo interface.

Required sections:

```text
1. Script input
2. Global style input
3. Generate video button
4. Video preview
5. Shot timeline table
6. User edit input
7. Apply edit button
8. Regeneration summary
```

The UI must clearly show:

```text
shot_001 -> preserved
shot_002 -> regenerated
shot_003 -> preserved
```

This is more important than visual polish.

Decision:

Use Streamlit instead of a custom frontend.

Alternatives considered:

- React frontend
- FastAPI plus separate UI
- Command-line demo only

Why rejected:

- React takes more time.
- FastAPI plus frontend adds extra integration work.
- CLI is less compelling for hackathon demos.

Benefits:

- Fast to build
- Easy video preview
- Easy table display
- Good enough for one-day submission

Drawbacks:

- Less polished than a custom UI
- Less production-like

Interview talking point:

> I optimized the MVP around proving the regeneration loop, so Streamlit was the right tradeoff.

---

### 4.2 LangGraph Workflow

Purpose:

Control the initial generation and user feedback loop.

Graph nodes:

```text
parse_script
plan_shots
build_prompts
generate_shots
compose_video
analyze_edit
find_affected_shots
rewrite_prompts
regenerate_shots
recompose_video
```

Initial generation flow:

```text
parse_script
-> plan_shots
-> build_prompts
-> generate_shots
-> compose_video
```

Edit flow:

```text
analyze_edit
-> find_affected_shots
-> rewrite_prompts
-> regenerate_shots
-> recompose_video
```

Decision:

Use LangGraph for orchestration.

Alternatives considered:

- Plain Python pipeline
- Fully autonomous agent
- Custom workflow graph

Why rejected:

- Plain Python is less expressive for the feedback loop.
- Fully autonomous agents are harder to control and debug.
- A custom workflow graph is unnecessary.

Benefits:

- Clear state transitions
- Human-in-the-loop workflow is easy to model
- Good interview explanation
- Future support for checkpoints and resumability

Drawbacks:

- More setup than plain functions
- Can become over-engineered if every tiny step becomes a node

Interview talking point:

> I used LangGraph because the project is a stateful feedback loop, not a one-shot generation pipeline.

---

## 5. State Design

### 5.1 VideoGraphState

This is the in-memory state passed through LangGraph.

```python
class VideoGraphState(TypedDict):
    project_id: str
    script: str
    global_style: str

    scenes: list[dict]
    shots: list[dict]

    user_edit: str | None
    edit_intent: dict | None
    affected_shot_ids: list[str]

    locked_audio_path: str | None
    final_video_path: str | None

    current_version: int
    status: str
```

Important distinction:

- LangGraph state is workflow state.
- JSON files are persistent project state.
- The shot manifest is the domain source of truth.

---

### 5.2 Project State

Path:

```text
projects/{project_id}/project_state.json
```

Example:

```json
{
  "project_id": "project_001",
  "script": "A detective enters an archive room...",
  "global_style": "cinematic noir",
  "current_version": 2,
  "locked_audio_path": "audio/background.mp3",
  "final_video_path": "final/final_v2.mp4",
  "created_at": "2026-06-02T10:00:00",
  "updated_at": "2026-06-02T10:20:00"
}
```

Purpose:

Stores project-level metadata.

---

### 5.3 Shot Manifest

Path:

```text
projects/{project_id}/shot_manifest.json
```

Example:

```json
[
  {
    "shot_id": "shot_001",
    "scene_id": "scene_001",
    "order": 1,
    "script_text": "A detective enters an old archive room.",
    "description": "Detective enters archive room",
    "characters": ["detective"],
    "location": "old archive room",
    "visual_style": "cinematic noir",
    "duration_sec": 4,
    "prompt": "Cinematic noir shot of a detective entering a dusty archive room...",
    "negative_prompt": "blurry, distorted face, inconsistent lighting",
    "asset_path": "shots/shot_001_v1.mp4",
    "version": 1,
    "status": "complete",
    "last_action": "preserved",
    "continuity": {
      "entry_context": "Start of scene",
      "exit_context": "Detective sees a glowing file"
    }
  }
]
```

Required fields:

```text
shot_id
scene_id
order
script_text
description
characters
location
visual_style
duration_sec
prompt
negative_prompt
asset_path
version
status
last_action
continuity
```

Decision:

Use shot-level state instead of full-video state.

Why:

Partial regeneration needs a mapping between script sections and generated assets.

---

## 6. Storage Layout

Use local files for the MVP.

```text
projects/
  project_001/
    project_state.json
    shot_manifest.json

    shots/
      shot_001_v1.mp4
      shot_002_v1.mp4
      shot_002_v2.mp4
      shot_003_v1.mp4

    final/
      final_v1.mp4
      final_v2.mp4

    audio/
      background.mp3
```

Decision:

Use JSON plus files for storage.

Alternatives considered:

- PostgreSQL
- MongoDB
- Vector database

Why rejected:

- Too much setup for a one-day build.
- The core technical risk is incremental regeneration, not database scaling.

Benefits:

- Easy to inspect
- Easy to debug
- Easy to demo
- No infrastructure required

Drawbacks:

- Not ideal for production scale
- Concurrent editing would be unsafe

Interview talking point:

> I chose local JSON because it made the editable state visible and kept the MVP focused on the hard part: partial regeneration.

---

## 7. Core Logic

### 7.1 Script Parser

Input:

```text
Raw script
```

Output:

```json
[
  {
    "scene_id": "scene_001",
    "scene_text": "...",
    "location": "archive room",
    "characters": ["detective"]
  }
]
```

MVP logic:

- Use an LLM to split the script into 3-6 cinematic shots.
- If LLM parsing fails, fall back to simple text chunking.

LLM prompt intent:

```text
Break this script into 3-6 cinematic shots. Return JSON only.
Each shot must include script_text, description, characters, location, duration_sec, and continuity notes.
```

Decision:

Use LLM for script parsing.

Why:

Script understanding is semantic and hard to solve with simple rules.

Drawback:

LLM may return invalid JSON.

Mitigation:

Validate output and fallback to rule-based splitting.

---

### 7.2 Shot Planner

Input:

```text
Scenes or raw script
```

Output:

```text
Canonical shot manifest entries
```

Logic:

1. Assign `shot_id`.
2. Assign `scene_id`.
3. Assign `order`.
4. Extract characters.
5. Extract location.
6. Assign duration.
7. Add continuity fields.

Shot ID format:

```text
shot_001
shot_002
shot_003
```

MVP constraint:

- Minimum shots: 3
- Maximum shots: 6
- Fixed duration per shot: 4 seconds

Reason:

This keeps generation fast and makes the feedback loop demoable.

---

### 7.3 Prompt Builder

Input:

```text
Shot metadata + global style
```

Output:

```text
Generation prompt per shot
```

Prompt template:

```text
{visual_style}. {description}.
Characters: {characters}.
Location: {location}.
Continuity: previous context: {entry_context}, next context: {exit_context}.
Duration: {duration_sec} seconds.
Camera: cinematic, stable, coherent.
```

Decision:

Build prompts from structured shot metadata.

Why:

This keeps generation prompts consistent and editable.

Interview talking point:

> Prompt generation is derived from structured state instead of being a loose text blob.

---

### 7.4 Shot Generator

Input:

```text
Shot prompt
```

Output:

```text
Shot video asset path
```

MVP generator options:

#### Option A: Gemini Video Generation

Use whichever Gemini video generation model/API is available in the environment to generate a short video clip per shot.

Pros:

- Best match for the project objective
- Stronger visual demo
- Keeps the system aligned with real script-to-video generation

Cons:

- May be slower
- May have API limits or availability issues
- May require polling or async job handling

#### Option B: Gemini Image Plus Motion

Use Gemini/image generation to create a still image per shot, then convert it into a short video using slow zoom/pan motion.

Pros:

- More reliable than full video generation
- Still visually meaningful
- Faster and cheaper than full video generation
- Good fallback for one-day demo

Cons:

- Not true video generation
- Motion is simple

#### Option C: Placeholder Generator

Generate simple video clips from text cards or colored cinematic frames.

Pros:

- Very reliable
- Fast
- Good for proving architecture when APIs fail

Cons:

- Less visually impressive

Recommended MVP:

Use this fallback order:

```text
1. Gemini video generation
2. Gemini image generation + motion
3. Placeholder clip generation
```

This keeps the demo resilient.

Implementation interface:

```python
def generate_shot(shot: dict, project_dir: str) -> str:
    ...
```

Internally:

```text
generate_shot
-> try Gemini video
-> if unavailable, try Gemini image + motion
-> if unavailable, create placeholder clip
```

Decision:

Use Gemini as the primary media generation provider, but keep a provider fallback chain.

Why:

The project should demonstrate real AI media generation, but a one-day demo cannot depend entirely on a slow or unavailable video API.

Interview talking point:

> I used Gemini as the primary generation provider, but isolated generation behind a provider interface so the feedback-loop architecture remains reliable even if video generation is unavailable.

Interview talking point:

> The core system is provider-independent: Gemini creates the assets, but the manifest and regeneration logic control what changes.

---

### 7.5 Video Composer

Input:

```text
Ordered shot asset paths
locked audio path
```

Output:

```text
final_v{n}.mp4
```

Logic:

1. Sort shots by `order`.
2. Load each shot asset.
3. Concatenate clips.
4. Add background music if available.
5. Export final video.

Use:

- MoviePy for simplicity
- FFmpeg if MoviePy has compatibility issues

MVP audio rule:

- Use one locked background music track.
- If no audio exists, compose without audio.
- Keep shot durations fixed to avoid sync issues.

Decision:

Preserve background music across edits.

Why:

Music continuity makes partial visual regeneration feel smoother.

Drawback:

If regenerated shot duration changes, sync may drift.

MVP mitigation:

Use fixed shot durations.

---

### 7.6 User Edit Analyzer

Input:

```text
User edit instruction + shot manifest
```

Example:

```text
Make the glowing file red instead of blue.
```

Output:

```json
{
  "edit_type": "visual_object_change",
  "target_objects": ["glowing file"],
  "target_characters": [],
  "target_location": null,
  "style_change": null,
  "requires_global_change": false
}
```

Decision:

Use LLM for edit understanding.

Why:

User feedback is usually vague natural language.

Drawback:

LLM interpretation can be wrong.

Mitigation:

Use deterministic filtering against the shot manifest after the LLM extracts intent.

---

### 7.7 Impact Analyzer

Input:

```text
edit_intent + shot_manifest
```

Output:

```text
affected_shot_ids
```

Rules:

```text
Object edit -> shots containing object
Character edit -> all shots containing character
Location edit -> all shots in that location
Global style edit -> all shots
Scene edit -> shots in that scene
Timing/action edit -> affected shot and maybe neighbor
```

Examples:

```text
Edit: Make the glowing file red.
Affected: shot containing the glowing file.
```

```text
Edit: Make the detective wear a red coat.
Affected: all shots containing the detective.
```

```text
Edit: Make the whole video darker.
Affected: all shots.
```

Decision:

Use hybrid LLM plus deterministic filtering.

Why:

The LLM understands the edit, but code controls what actually regenerates.

Interview talking point:

> The agent interprets the user, but deterministic logic owns the timeline.

---

### 7.8 Prompt Rewriter

Input:

```text
affected shots + user edit + neighbor continuity
```

Output:

```text
Updated prompts for affected shots
```

Logic:

For each affected shot:

1. Keep the original prompt structure.
2. Add the user edit.
3. Add continuity constraints from previous and next shot.
4. Keep the same duration.
5. Increment the version.

Example:

Before:

```text
Close-up of a blue glowing file on a desk.
```

After:

```text
Close-up of a red glowing file on a desk.
Preserve same archive room, same noir lighting, same camera framing.
Previous shot: detective enters archive room.
Next shot: lights go out.
```

Decision:

Use neighboring shots as continuity context.

Why:

This reduces jarring visual transitions after partial regeneration.

---

### 7.9 Regenerator

Input:

```text
affected_shot_ids + shot_manifest
```

Output:

```text
New shot assets + updated manifest
```

Logic:

For each affected shot:

1. Set `status` to `regenerating`.
2. Increment `version`.
3. Generate a new asset.
4. Update `asset_path`.
5. Set `last_action` to `regenerated`.

For unaffected shots:

```text
last_action = preserved
asset_path unchanged
version unchanged
```

Important:

Never overwrite old generated files.

Use:

```text
shot_002_v1.mp4
shot_002_v2.mp4
```

Decision:

Version generated assets instead of overwriting.

Why:

This supports comparison, debugging, and future undo.

Interview talking point:

> Creative tools need history. Versioning also makes regeneration auditable.

---

### 7.10 Recomposer

Input:

```text
Updated shot manifest
```

Output:

```text
final_v{n}.mp4
```

Logic:

1. Use the latest `asset_path` for each shot.
2. Preserve locked audio.
3. Compose final video.
4. Update project state.

---

## 8. Function Design

Since Streamlit can call Python functions directly, a separate FastAPI backend is not required for the MVP.

Recommended public functions:

```python
def create_project(script: str, global_style: str) -> VideoGraphState:
    ...

def generate_initial_video(project_id: str) -> VideoGraphState:
    ...

def apply_user_edit(project_id: str, instruction: str) -> VideoGraphState:
    ...

def load_project_state(project_id: str) -> dict:
    ...

def load_shot_manifest(project_id: str) -> list[dict]:
    ...

def save_project_state(project_id: str, state: dict) -> None:
    ...

def save_shot_manifest(project_id: str, shots: list[dict]) -> None:
    ...
```

Decision:

Skip FastAPI for the MVP.

Why:

The project needs a working core loop quickly. Streamlit plus direct Python functions is enough.

Drawback:

Less production-like.

Interview talking point:

> I kept function boundaries clean so the same logic can later be exposed through FastAPI.

---

## 9. Recommended File Structure

```text
videogen/
  app.py

  src/
    graph.py
    state.py
    storage.py
    script_parser.py
    shot_planner.py
    prompt_builder.py
    generator.py
    composer.py
    edit_analyzer.py
    impact_analyzer.py
    regenerator.py

  projects/
    .gitkeep

  assets/
    default_music.mp3

  requirements.txt
  README.md
  PROJECT_SPEC.md
```

File responsibilities:

```text
app.py:
  Streamlit UI.

src/graph.py:
  LangGraph workflow definition.

src/state.py:
  TypedDict/dataclasses for project state and shots.

src/storage.py:
  JSON read/write helpers.

src/script_parser.py:
  LLM or fallback script parsing.

src/shot_planner.py:
  Creates canonical shot list.

src/prompt_builder.py:
  Converts shot metadata to prompts.

src/generator.py:
  Creates shot assets using Gemini video generation when available, Gemini image-plus-motion as fallback, and placeholder clips as final fallback.

src/composer.py:
  Concatenates shots and adds audio.

src/edit_analyzer.py:
  Converts user edit into structured intent.

src/impact_analyzer.py:
  Finds affected shots.

src/regenerator.py:
  Updates prompts, regenerates shots, and versions assets.
```

---

## 10. MVP Constraints

Use these constraints to keep the system buildable in one day:

```text
Max shots: 6
Min shots: 3
Fixed shot duration: 4 seconds
One background music track
One active project initially
Local file storage only
No real-time streaming
No complex timeline editor
No database
No multi-user support
```

These are intentional constraints, not missing features.

Interview talking point:

> I constrained the MVP around the core behavior: state-aware incremental regeneration.

---

## 11. Failure Handling

### Invalid LLM JSON

Fallback:

```text
Split the script into 3 chunks manually and create one shot per chunk.
```

### No Affected Shots Found

Fallback:

```text
Ask the LLM to choose the best matching shot.
If still none, regenerate all shots.
```

### Video Generation Fails

Fallback:

```text
Create a placeholder clip with the shot description text.
```

### Composer Fails

Fallback:

```text
Show generated shot assets individually.
```

### Audio Missing

Fallback:

```text
Compose video without audio.
```

---

## 12. Demo Scenario

Use this script:

```text
A detective enters an old archive room. Dust floats in the air as she walks between shelves. She finds a glowing blue file on a wooden desk. Suddenly the lights flicker and go out.
```

Expected shots:

```text
shot_001: detective enters archive room
shot_002: detective walks between shelves
shot_003: glowing blue file on desk
shot_004: lights flicker and go out
```

User edit:

```text
Make the glowing file red instead of blue.
```

Expected result:

```text
Affected: shot_003
Preserved: shot_001, shot_002, shot_004
Regenerated: shot_003_v2.mp4
Final: final_v2.mp4
Music: unchanged
```

Second user edit:

```text
Make the detective look scared throughout the archive scene.
```

Expected result:

```text
Affected: shot_001, shot_002, shot_003, shot_004
Reason: detective appears in all archive shots
```

This proves both local and broad regeneration.

---

## 13. Senior Engineering Decisions

### Decision 1: Shot Manifest Is The Source Of Truth

Why chosen:

- Enables partial regeneration
- Makes the system inspectable
- Maps script sections to generated assets

Alternatives considered:

- Treat final video as source of truth
- Store only prompts
- Store only generated files

Why rejected:

- Final video is opaque.
- Prompts alone do not track assets or versions.
- Files alone do not explain generation logic.

Benefits:

- Editable state
- Debuggable outputs
- Easier demo explanation

Drawbacks:

- More metadata to maintain

Interview defense:

> Without an intermediate representation, the video is just a blob. The manifest makes it editable.

---

### Decision 2: Shot-Level Regeneration

Why chosen:

- Best balance between precision and simplicity
- Smaller than scene-level regeneration
- Simpler than frame-level editing

Alternatives considered:

- Full video regeneration
- Scene-level regeneration
- Frame-level regeneration

Why rejected:

- Full video regeneration is slow and costly.
- Scene regeneration may redo too much.
- Frame regeneration is too complex for MVP.

Benefits:

- Faster edits
- Lower cost
- Strong demo value

Drawbacks:

- Transitions between shots may still need smoothing

Interview defense:

> A shot is the smallest meaningful cinematic unit that still maps cleanly to script intent.

---

### Decision 3: LangGraph For Workflow

Why chosen:

- The system is a feedback loop
- State transitions need to be explicit
- It gives a strong agentic-system explanation

Alternatives considered:

- Plain Python functions only
- Fully autonomous agent
- Custom graph implementation

Why rejected:

- Plain Python is less expressive for loops.
- Fully autonomous agents are less controllable.
- Custom graph logic is unnecessary.

Benefits:

- Clear orchestration
- Easy to extend
- Good interview story

Drawbacks:

- Slight setup overhead

Interview defense:

> LangGraph models the human-in-the-loop regeneration process explicitly.

---

### Decision 4: Streamlit For UI

Why chosen:

- Fastest path to a demo
- Native support for forms, tables, and video preview

Alternatives considered:

- React frontend
- CLI-only demo

Why rejected:

- React costs too much time.
- CLI does not demo video workflows well.

Benefits:

- Fast implementation
- Good enough for hackathon demo

Drawbacks:

- Less polished

Interview defense:

> I intentionally spent time on the core regeneration loop instead of a custom frontend.

---

### Decision 5: Local JSON Storage

Why chosen:

- Easy to implement
- Easy to inspect
- No infrastructure needed

Alternatives considered:

- PostgreSQL
- MongoDB
- Vector database

Why rejected:

- The MVP does not need database complexity.

Benefits:

- Simple
- Demo-friendly
- Debuggable

Drawbacks:

- Not scalable
- Not safe for concurrent writes

Interview defense:

> I avoided database complexity until the core architecture was validated.

---

### Decision 6: Hybrid LLM And Deterministic Logic

Why chosen:

- LLM handles semantic interpretation
- Deterministic logic controls regeneration boundaries

Alternatives considered:

- Fully deterministic rules
- Fully agentic regeneration

Why rejected:

- Rules struggle with vague edits.
- Fully agentic systems are hard to control.

Benefits:

- Flexible but auditable
- Better safety
- Better explainability

Drawbacks:

- Requires validation of LLM output

Interview defense:

> The agent reasons, but deterministic code owns the timeline.

---

### Decision 7: Preserve Background Music

Why chosen:

- Audio continuity makes the final video feel more coherent
- Avoids regenerating music after every edit

Alternatives considered:

- Regenerate music every time
- Ignore audio

Why rejected:

- Regenerating music is costly and inconsistent.
- Ignoring audio weakens the demo.

Benefits:

- Better perceived continuity
- Lower cost

Drawbacks:

- Shot durations must remain stable

Interview defense:

> Stable audio is a low-cost way to make partial visual regeneration feel continuous.

---

### Decision 8: Version Every Generated Shot

Why chosen:

- Supports comparison
- Supports debugging
- Enables future undo

Alternatives considered:

- Overwrite old files
- Store only final videos

Why rejected:

- Overwrites make debugging hard.
- Final videos alone do not explain changes.

Benefits:

- Auditable creative history
- Easy before/after demo

Drawbacks:

- Uses more storage

Interview defense:

> Versioning makes creative iteration auditable.

---

## 14. One-Day Build Plan

### First 2 Hours

Build:

```text
File structure
State models
Storage helpers
Basic Streamlit UI
Script input
Shot manifest display
```

Goal:

Have a project created and visible as structured shots.

---

### First 4 Hours

Build:

```text
LangGraph initial flow
Script parser
Shot planner
Prompt builder
Gemini media generator with fallback clip generation
```

Goal:

Generate shot assets from a script and show them in the preview.

---

### First 6 Hours

Build:

```text
Composer
Final video preview
Project state updates
Version tracking
```

Goal:

Initial generated video works.

---

### First 8 Hours

Build:

```text
User edit input
Edit analyzer
Impact analyzer
Prompt rewriter
Regenerate affected shots only
Recompose final video
```

Goal:

Core feedback loop works.

---

### Final Polish

Add:

```text
Regeneration summary
Affected/preserved labels
Version numbers
Simple README
Demo script
```

Goal:

Make the system explainable.

---

## 15. Postponed Features

Do not build these for the MVP:

```text
Full timeline editor
Multi-agent creative crew
Database
Authentication
Real-time streaming
Multi-user collaboration
Advanced audio remixing
Frame-level edits
Perfect character consistency
Complex dependency graph
```

These are architectural decoration for the one-day version.

---

## 16. Final MVP Definition

Build exactly this:

```text
Streamlit app where:
1. User enters a script.
2. System creates a 3-6 shot manifest.
3. System generates per-shot clips using Gemini when available.
4. System composes the final video.
5. User enters an edit.
6. System identifies affected shots.
7. Only affected shots regenerate.
8. Final video is recomposed.
9. UI shows affected vs preserved shots.
```

This is the core project.

Everything else is secondary.

Final architecture challenge:

> Is this component solving a real problem or is it architectural decoration?

For this MVP, every component should directly support one of these:

- Script-to-shot planning
- Shot-level state tracking
- Incremental regeneration
- Video recomposition
- Demo explainability
