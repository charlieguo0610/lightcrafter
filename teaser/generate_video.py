"""
generate_video.py — Generate a narrated teaser video from teaser_slides.html

Pipeline:
  1. Generate per-step narration audio via edge-tts
  2. Record the browser live via Playwright video recording (captures CSS animations)
  3. Build a synced audio track and merge with the recording via ffmpeg

Requirements:
  pip install edge-tts playwright
  playwright install chromium
  ffmpeg must be on PATH

Run from this directory:
  python generate_video.py

IMPORTANT: NARRATION must contain exactly one entry per deck "state" (state 0 is
shown on load, every entry after that is one ArrowRight press). The current deck
(teaser_slides.html) has 20 states:
  S0:2  S1:2  S2:3  S3:3  S4:2  S5:2  S6:2  S7:2  S8:2  = 20
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

WORK_DIR = Path(__file__).parent          # .../website-arxiv/teaser
SERVE_ROOT = WORK_DIR.parent              # .../website-arxiv  (so /static/... resolves)
BUILD_DIR = WORK_DIR / "_video_build"
AUDIO_DIR = BUILD_DIR / "audio"
RECORDING_DIR = BUILD_DIR / "recording"
OUTPUT_FILE = WORK_DIR / "teaser_video.mp4"
SLIDES_URL_PATH = "/teaser/teaser_slides.html"

VOICE = "en-US-AndrewMultilingualNeural"
RATE = "+12%"

ANIM_SETTLE = 0.8   # seconds to let CSS animation play before "narration starts"
POST_SILENCE = 0.3  # brief silence after each narration clip

# ── narration script: one entry per state (state 0 shown on load) ─────────────
NARRATION = [
    # Slide 0: Title (2 states)
    ("LightCrafter: PBR-conditioned video diffusion refinement for controllable and consistent relighting.", 0.4),
    ("We reframe video relighting as the translation of a physically-based rendering proxy, "
     "gaining precise lighting control and long-form temporal consistency.", 0.5),

    # Slide 1: What is video relighting (2 states)
    ("First, what is video relighting?", 0.2),
    ("Given an input video and a target illumination, we re-render the whole video under the new lighting, "
     "with consistent shadows, reflections, and materials.", 0.4),

    # Slide 2: Why is it hard / two paradigms (3 states)
    ("This is hard, because it demands both long-form temporal consistency and a physically grounded "
     "understanding of light transport. Prior work follows two paradigms.", 0.3),
    ("The first explicitly reconstructs scene properties and re-renders them, but reconstructions are noisy "
     "and it struggles with effects like global illumination.", 0.4),
    ("The second frames relighting as generative video-to-video translation, which limits control and "
     "temporal stability, and depends on scarce paired training data.", 0.5),

    # Slide 3: Our key insight (3 states)
    ("Our key insight.", 0.2),
    ("Rather than translating the input video directly, we translate a PBR proxy rendered under the target lighting.", 0.3),
    ("This bakes the lighting target into the proxy, giving intricate lighting control, long-form temporal "
     "consistency, and no need to teach the model about environment maps.", 0.5),

    # Slide 4: Method overview (2 states)
    ("Here is how it works.", 0.2),
    ("We recover a relightable scene state, render a frame-aligned PBR proxy under the target lighting, and a "
     "video diffusion refiner turns it into a photorealistic, temporally coherent result.", 0.6),

    # Slide 5: Proxy first, then refine (2 states)
    ("The PBR proxy already captures most of the scene-light interaction.", 0.3),
    ("The diffusion refiner then removes rendering artifacts and adds hard-to-model effects like global illumination.", 0.5),

    # Slide 6: Comparison (2 states)
    ("Against prior state of the art, our results respond more faithfully to the target lighting.", 0.3),
    ("Baselines often bake in source lighting or drift over time, while ours stays consistent.", 0.5),

    # Slide 7: Applications (2 states)
    ("Because the proxy is explicit, we also support applications like environment relighting and light insertion.", 0.3),
    ("These edits start from a clean scene render and add new light sources.", 0.5),

    # Slide 8: Takeaway (2 states)
    ("We outperform prior state of the art on real-world relighting benchmarks, and contribute a new synthetic benchmark.", 0.3),
    ("PBR proxies plus video diffusion give us controllable, consistent video relighting. Thank you.", 1.3),
]

# ── helpers ──────────────────────────────────────────────────────────────────

def check_deps():
    missing = []
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        missing.append("edge-tts")
    try:
        import playwright  # noqa: F401
    except ImportError:
        missing.append("playwright")
    if shutil.which("ffmpeg") is None:
        print("ERROR: ffmpeg not found on PATH.")
        sys.exit(1)
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
    try:
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])


def get_audio_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, text=True,
    )
    info = json.loads(r.stdout)
    return float(info["format"]["duration"])


def start_http_server(directory, port=8765):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(directory), **kw)
        def log_message(self, *a):
            pass
    server = HTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


# ── step 1: generate audio ──────────────────────────────────────────────────

async def generate_audio():
    import edge_tts

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    durations = []

    for i, (text, _) in enumerate(NARRATION):
        out = AUDIO_DIR / f"seg_{i:02d}.mp3"
        if not text.strip():
            durations.append(0.0)
            print(f"  seg_{i:02d}.mp3  (silence — 0.0s)")
            continue
        if out.exists() and out.stat().st_size > 0:
            dur = get_audio_duration(out)
            durations.append(dur)
            print(f"  [cached] seg_{i:02d}.mp3  ({dur:.1f}s)")
            continue
        comm = edge_tts.Communicate(text, VOICE, rate=RATE)
        await comm.save(str(out))
        dur = get_audio_duration(out)
        durations.append(dur)
        print(f"  seg_{i:02d}.mp3  ({dur:.1f}s)")

    return durations


# ── step 2: record browser with animations ──────────────────────────────────

async def record_video(durations, port=8765):
    from playwright.async_api import async_playwright

    RECORDING_DIR.mkdir(parents=True, exist_ok=True)
    url = f"http://127.0.0.1:{port}{SLIDES_URL_PATH}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(RECORDING_DIR),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        await page.goto(url)
        await page.wait_for_load_state("networkidle")

        await asyncio.sleep(1.5)

        dur_0 = durations[0]
        extra_0 = NARRATION[0][1]
        wait_0 = ANIM_SETTLE + dur_0 + POST_SILENCE + extra_0
        print(f"  state 00: wait {wait_0:.1f}s")
        await asyncio.sleep(wait_0)

        for i in range(1, len(NARRATION)):
            await page.keyboard.press("ArrowRight")
            dur_i = durations[i]
            extra_i = NARRATION[i][1]
            wait_i = ANIM_SETTLE + dur_i + POST_SILENCE + extra_i
            print(f"  state {i:02d}: → + wait {wait_i:.1f}s")
            await asyncio.sleep(wait_i)

        await asyncio.sleep(2.0)

        await context.close()
        await browser.close()

    recordings = list(RECORDING_DIR.glob("*.webm"))
    if not recordings:
        print("ERROR: No recording file found!")
        sys.exit(1)
    recording_path = recordings[0]
    print(f"  Recording: {recording_path.name}")
    return recording_path


# ── step 3: build audio track & merge ────────────────────────────────────────

def build_audio_and_merge(durations, recording_path):
    padded_dir = BUILD_DIR / "padded"
    padded_dir.mkdir(exist_ok=True)
    concat_entries = []

    lead_silence = 1.5 + ANIM_SETTLE
    lead_path = padded_dir / "lead_silence.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", str(lead_silence), "-q:a", "0", str(lead_path),
    ], capture_output=True)
    concat_entries.append(f"file '{lead_path}'")

    for i, (dur_audio, (text, extra_pause)) in enumerate(zip(durations, NARRATION)):
        seg_audio = AUDIO_DIR / f"seg_{i:02d}.mp3"
        padded_out = padded_dir / f"padded_{i:02d}.wav"

        if i < len(NARRATION) - 1:
            tail = POST_SILENCE + extra_pause + ANIM_SETTLE
        else:
            tail = POST_SILENCE + extra_pause

        if not text.strip() or dur_audio == 0:
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                "-t", str(tail + extra_pause), "-q:a", "0", str(padded_out),
            ], capture_output=True)
        else:
            subprocess.run([
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                "-i", str(seg_audio),
                "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                "-filter_complex",
                f"[1:a]aresample=24000,volume=2.0[narr];"
                f"[2]atrim=0:{tail}[post];"
                f"[narr][post]concat=n=2:v=0:a=1[out]",
                "-map", "[out]", "-ar", "24000", str(padded_out),
            ], capture_output=True)
        concat_entries.append(f"file '{padded_out}'")

    trail_path = padded_dir / "trail_silence.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", "2.0", "-q:a", "0", str(trail_path),
    ], capture_output=True)
    concat_entries.append(f"file '{trail_path}'")

    audio_list = BUILD_DIR / "audio_concat.txt"
    audio_list.write_text("\n".join(concat_entries))

    full_audio = BUILD_DIR / "full_audio.wav"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(audio_list), "-c:a", "pcm_s16le", str(full_audio),
    ], capture_output=True)

    print(f"\n  Merging recording + audio...")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(recording_path),
        "-i", str(full_audio),
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        str(OUTPUT_FILE),
    ], check=True)

    dur_info = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(OUTPUT_FILE)],
        capture_output=True, text=True,
    )
    total = float(json.loads(dur_info.stdout)["format"]["duration"])
    print(f"\n  Done! {OUTPUT_FILE.name} ({total:.0f}s)")


# ── main ─────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  LightCrafter Teaser Video Generator")
    print("=" * 60)

    print("\n[0/3] Checking dependencies...")
    check_deps()

    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n[1/3] Generating narration audio ({len(NARRATION)} segments)...")
    durations = await generate_audio()

    print(f"\n[2/3] Recording browser with animations...")
    server = start_http_server(SERVE_ROOT)
    recording_path = await record_video(durations)
    server.shutdown()

    print(f"\n[3/3] Building audio track & merging...")
    build_audio_and_merge(durations, recording_path)

    print(f"\n  Output: {OUTPUT_FILE}")
    print(f"  Build artifacts in: {BUILD_DIR}")

if __name__ == "__main__":
    asyncio.run(main())
