"""Shot asset generation.

This module handles shot generation via Gemini video and image-plus-motion APIs only.
LLM-backed generation is required; no fallback placeholders or text-based artifacts.
"""

from __future__ import annotations

import os
import time
from io import BytesIO
from pathlib import Path

from .gemini_agent import ask_gemini_agent, get_gemini_api_key, get_genai_client
from .state import Shot
from .storage import get_project_subdir


DEFAULT_VIDEO_MODEL = "veo-2.0-generate-001"
DEFAULT_IMAGE_MODEL = "imagen-4.0-generate-001"
DEFAULT_VIDEO_TIMEOUT_SEC = 600
DEFAULT_VIDEO_POLL_SEC = 10


def generate_shot(shot: Shot, project_id: str, base_dir: str | Path = ".") -> str:
    """Generate one shot asset and return a path relative to the project dir."""

    project_dir = get_project_subdir(project_id, "shots", base_dir).parent
    shots_dir = project_dir / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{shot['shot_id']}_v{shot['version']}.mp4"
    output_path = shots_dir / filename

    if try_gemini_video(shot, output_path):
        return f"shots/{filename}"
    if try_gemini_image_plus_motion(shot, output_path):
        return f"shots/{filename}"

    raise RuntimeError(
        f"Failed to generate shot {shot['shot_id']}: "
        "Gemini video and image generation both failed. "
        "Check GEMINI_API_KEY and provider status."
    )


def try_gemini_video(shot: Shot, output_path: Path) -> bool:
    """Try real Gemini/Veo video generation when configured."""

    client = get_genai_client()
    if client is None or not get_gemini_api_key():
        return False
    prompt = ask_gemini_agent(
        "You are a video generation planning agent. Return concise provider instructions only.",
        build_gemini_video_prompt(shot, output_path),
    ) or shot["prompt"]

    try:
        from google.genai import types

        operation = client.models.generate_videos(
            model=os.getenv("GEMINI_VIDEO_MODEL", DEFAULT_VIDEO_MODEL),
            prompt=prompt,
            config=types.GenerateVideosConfig(
                numberOfVideos=1,
                durationSeconds=bounded_duration(shot["duration_sec"]),
                aspectRatio=os.getenv("GEMINI_VIDEO_ASPECT_RATIO", "16:9"),
                negativePrompt=shot.get("negative_prompt") or None,
                enhancePrompt=True,
            ),
        )
        operation = wait_for_video_operation(client, operation)
        generated_video = first_generated_video(operation)
        if generated_video is None:
            return False

        output_path.write_bytes(client.files.download(file=generated_video))
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception as exc:
        write_provider_error(output_path, "Gemini video generation failed", exc)
        return False


def try_gemini_image_plus_motion(shot: Shot, output_path: Path) -> bool:
    """Try real Gemini image generation plus simple motion when configured."""

    client = get_genai_client()
    if client is None or not get_gemini_api_key():
        return False
    prompt = ask_gemini_agent(
        "You are an image generation planning agent. Return concise image and motion instructions only.",
        build_gemini_image_motion_prompt(shot, output_path),
    ) or shot["prompt"]

    try:
        from google.genai import types

        response = client.models.generate_images(
            model=os.getenv("GEMINI_IMAGE_MODEL", DEFAULT_IMAGE_MODEL),
            prompt=prompt,
            config=types.GenerateImagesConfig(
                numberOfImages=1,
                aspectRatio=os.getenv("GEMINI_IMAGE_ASPECT_RATIO", "16:9"),
                outputMimeType="image/png",
            ),
        )
        generated_images = response.generated_images or []
        if not generated_images or not generated_images[0].image:
            return False

        image_bytes = generated_images[0].image.image_bytes
        if not image_bytes:
            return False

        create_motion_clip_from_image(image_bytes, shot, output_path)
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception as exc:
        write_provider_error(output_path, "Gemini image generation failed", exc)
        return False


def wait_for_video_operation(client, operation):
    """Poll a Veo long-running operation until completion or timeout."""

    timeout_sec = int(os.getenv("GEMINI_VIDEO_TIMEOUT_SEC", str(DEFAULT_VIDEO_TIMEOUT_SEC)))
    poll_sec = int(os.getenv("GEMINI_VIDEO_POLL_SEC", str(DEFAULT_VIDEO_POLL_SEC)))
    deadline = time.monotonic() + timeout_sec
    while not getattr(operation, "done", False):
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Gemini video generation timed out after {timeout_sec} seconds")
        time.sleep(max(1, poll_sec))
        operation = client.operations.get(operation)
    return operation


def first_generated_video(operation):
    """Return the first generated video from a completed operation."""

    response = getattr(operation, "response", None)
    generated_videos = getattr(response, "generated_videos", None) if response else None
    if not generated_videos:
        return None
    video = getattr(generated_videos[0], "video", None)
    return video or generated_videos[0]


def bounded_duration(duration_sec: int) -> int:
    """Keep requested shot duration inside common Veo API limits."""

    return max(5, min(int(duration_sec), 8))


def create_motion_clip_from_image(image_bytes: bytes, shot: Shot, output_path: Path) -> None:
    """Create a simple zoom MP4 from a Gemini-generated still image."""

    import imageio.v2 as imageio
    import numpy as np
    from PIL import Image

    width, height = 1280, 720
    duration = shot["duration_sec"]
    fps = 24

    source = Image.open(BytesIO(image_bytes)).convert("RGB")
    source.thumbnail((width * 2, height * 2))
    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    x = (width - source.width) // 2
    y = (height - source.height) // 2
    canvas.paste(source, (x, y))

    writer = imageio.get_writer(str(output_path), fps=fps, codec="libx264", macro_block_size=16)
    try:
        total_frames = duration * fps
        for frame_index in range(total_frames):
            progress = frame_index / max(total_frames - 1, 1)
            scale = 1.0 + progress * 0.08
            crop_width = int(width / scale)
            crop_height = int(height / scale)
            left = (width - crop_width) // 2
            top = (height - crop_height) // 2
            frame = canvas.crop((left, top, left + crop_width, top + crop_height))
            frame = frame.resize((width, height), Image.Resampling.LANCZOS)
            writer.append_data(np.array(frame))
    finally:
        writer.close()


def write_provider_error(output_path: Path, message: str, exc: Exception) -> None:
    """Persist provider errors next to the requested media path for debugging."""

    output_path.with_suffix(".provider_error.txt").write_text(
        f"{message}\n{type(exc).__name__}: {exc}",
        encoding="utf-8",
    )





def build_gemini_video_prompt(shot: Shot, output_path: Path) -> str:
    """Build the non-LangGraph Gemini prompt for a shot video attempt.

    The prompt should preserve the exact shot identity and ask the provider to
    render a single coherent shot matching the existing metadata.
    """

    return (
        f"Create one {shot['duration_sec']}-second cinematic video shot for {shot['shot_id']}.\n"
        f"Shot description: {shot['description']}\n"
        f"Primary prompt: {shot['prompt']}\n"
        f"Negative prompt: {shot['negative_prompt']}\n"
        f"Preserve the exact shot identity, characters, location, lighting, and camera direction.\n"
        f"Render a single coherent shot with no unrelated redesign or extra scenes.\n"
        f"Output target: {output_path.name}"
    )


def build_gemini_image_motion_prompt(shot: Shot, output_path: Path) -> str:
    """Build the non-LangGraph Gemini prompt for image-plus-motion fallback.

    The prompt asks for a tightly matched still image plus subtle motion that
    stays faithful to the original shot.
    """

    return (
        f"Create a still image concept and subtle camera motion for {shot['shot_id']}.\n"
        f"Shot description: {shot['description']}\n"
        f"Primary prompt: {shot['prompt']}\n"
        f"Negative prompt: {shot['negative_prompt']}\n"
        f"Preserve the same shot composition, character appearance, location, and visual mood.\n"
        f"Use only gentle motion that supports the existing shot rather than redesigning it.\n"
        f"Duration: {shot['duration_sec']} seconds.\n"
        f"Output target: {output_path.name}"
    )



