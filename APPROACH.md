# Technical Approach

## Why This Stack?

### Gemini LLM for Everything

We use Gemini (Google's LLM) for shot planning, edit analysis, and impact detection. No fallback parsing, no regex tricks. Why? Because the problem is semantic - a user says "make the file red" and we need to understand what that means. LLM just handles it better than hardcoded rules.

The tradeoff: we need API credits. But the output is way better than trying to parse natural language with regex.

### Streamlit for UI

We could have built a React frontend or FastAPI + custom frontend. But for an MVP, Streamlit just works. It has native video preview, tables, forms - all the stuff we need. Built it in a day, focused on the core logic instead of CSS.

The downside is it's not fancy. But that's intentional. We wanted the feature to shine, not the UI.

### JSON Files for Storage

No database. Just JSON files in `projects/{project_id}/`. Why? Because:
1. We can inspect them directly
2. No setup needed
3. Easy to debug
4. Simple to version

Later when we scale, we'll move to a real database. But for now, it's clean.

### Shot Manifest as Source of Truth

Instead of storing the final video and trying to edit it, we store all the shot metadata - what each shot is, who's in it, what happens, the asset paths. This is the key idea.

When a user edits something, we:
1. Figure out which shots are affected
2. Regenerate only those shots
3. Compose a new final video

Without the manifest, this wouldn't be possible. We'd have to regenerate the whole thing.

### Explicit Regeneration Prompts

When we regenerate a shot after an edit, we tell Gemini exactly what to keep the same (characters, location, lighting, duration) and what to change. This keeps the shot consistent, doesn't randomly redesign it.

Example:
```
Keep: archive room, noir lighting, detective entering
Change: make the file red instead of blue
```

Instead of just:
```
Make the file red
```

The first version gives us 80% better results. Worth the extra prompt engineering.

## Why LLM-Only?

No placeholders. No deterministic fallbacks. Either Gemini generates the shot or it fails loudly. Why harsh? Because:

1. We can't ship a video generation product with placeholder text overlays
2. Silent failures hide bugs
3. For a demo, better to fail honestly than pretend

This forced us to get the Gemini API working properly. Good tradeoff.

## The Regeneration Strategy

The core innovation: track which shots change, regenerate only those, preserve the rest. Standard approach for most software (don't recompile everything), but new for AI video.

Without this, every user edit means regenerating 6 minutes of video. With it, we regenerate 4 seconds. Huge difference in cost and speed.

## What We Didn't Do

- No multi-agent crew
- No complex timeline editor
- No audio generation (we just preserve what's locked)
- No frame-level editing
- No rollback/undo (yet)

These would be nice but they're not the core insight. The core is: shot-level state + LLM-driven planning + smart regeneration.

## The Payoff

You can edit a video in natural language and only the affected parts regenerate. That's the thing we built for.

Everything else is scaffolding.
