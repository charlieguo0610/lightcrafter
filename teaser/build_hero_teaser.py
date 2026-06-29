"""
build_hero_teaser.py — Longer cinematic teaser for the hero / Twitter.

  PART 1  METHOD (sequential, full-screen, per subject = Car, Dancing, Human):
          Input -> Intrinsics Decomposition -> Geometry Reconstruction
                -> Relighting via PBR (round env-ball) -> Diffusion Refinement,
          chained with diagonal wipes and a per-stage label.
  PART 2  IN-THE-WILD: each scene as a 3-panel strip (Input | PBR+env-ball | Refinement),
          montaged with cross-dissolves to convey internet-scale generality.
  PART 3  END CARD: "LightCrafter" on black for a clean loop.

Run:  python build_hero_teaser.py     (needs ffmpeg + Pillow)
Output: ../static/videos/teaser.mp4
"""

import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import os

ROOT = Path(__file__).parent.parent
GAL = ROOT / "static/videos/gallery"
ENV = ROOT / "static/images/envmaps"
BUILD = Path(__file__).parent / "_hero_build"
OUT = ROOT / "static/videos/teaser.mp4"

W, H = 1920, 1080
FPS = 30
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"

# Content box: videos are fit (no crop) inside this, then padded onto the WxH canvas.
CONTENT_W, CONTENT_H = 1440, 960

L = 2.0          # method stage clip length (s) -- slower so each stage is readable
WIPE = 0.5       # diagonal wipe duration between stages
SUBJ_FADE = 0.5  # cross-dissolve between subjects
WILD_L = 2.4     # in-the-wild strip length
WILD_FADE = 0.45

# Method subjects (full pipeline assets all present). geo = source-px crop on 960x720 geometry.
SUBJECTS = [
    {"name": "Car",     "dir": "car-light-insertion", "ball": "satara_night_no_lamps_2k_ball.png", "geo": (380, 253, 300, 315)},
    {"name": "Dancing", "dir": "lalaland",            "ball": "kiara_5_noon_2k_ball.png",          "geo": (470, 313, 330, 175)},
    {"name": "Human",   "dir": "human",               "ball": "kiara_5_noon_2k_ball.png",          "geo": (560, 373, 340, 130)},
]

# In-the-wild scenes (3-panel: input | pbr+ball | relit). illum1 = autumn_field_puresky.
WILD = [
    "in-the-wild-scene-paper/scene_1",
    "in-the-wild-scene-paper/scene_7",
    "in-the-wild-scene-paper/scene_9",
    "in-the-wild-scene-paper/europe_building",
    "in-the-wild-scene-paper/temple",
]
WILD_BALL = "autumn_field_puresky_2k_ball.png"

ENC = ["-r", str(FPS), "-c:v", "libx264", "-crf", "18", "-preset", "fast",
       "-pix_fmt", "yuv420p", "-video_track_timescale", str(FPS * 512)]


def run(args):
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG ERROR:\n", " ".join(str(a) for a in args))
        print(r.stderr[-2500:])
        raise SystemExit(1)


def cover(w, h):
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},format=yuv420p,setsar=1"


# Fit a clip (no crop) into the CONTENT box, then pad onto the WxH black canvas.
CSCALE = (f"scale={CONTENT_W}:{CONTENT_H}:force_original_aspect_ratio=decrease,"
          f"pad={CONTENT_W}:{CONTENT_H}:(ow-iw)/2:(oh-ih)/2:color=black,fps={FPS},format=yuv420p,setsar=1")
PADWH = f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black"
FITPAD = CSCALE + "," + PADWH


def dt(label):
    safe = label.replace("'", "")
    return (f"drawtext=fontfile={FONT}:text='{safe}':fontcolor=white:fontsize=54:"
            f"box=1:boxcolor=black@0.55:boxborderw=18:x=(w-text_w)/2:y=h-text_h-70")


TITLE_DT = (f"drawtext=fontfile={FONT}:text='In-the-Wild Relighting':fontcolor=white:fontsize=58:"
            f"box=1:boxcolor=black@0.55:boxborderw=18:x=(w-text_w)/2:y=80")


def make_masks():
    cw, ch = CONTENT_W, CONTENT_H
    o = 0.12 * cw
    c = [0.25 * cw, 0.5 * cw, 0.75 * cw]
    bnd = [(ci + o, ci - o) for ci in c]
    polys = [
        [(0, 0), (bnd[0][0], 0), (bnd[0][1], ch), (0, ch)],
        [(bnd[0][0], 0), (bnd[1][0], 0), (bnd[1][1], ch), (bnd[0][1], ch)],
        [(bnd[1][0], 0), (bnd[2][0], 0), (bnd[2][1], ch), (bnd[1][1], ch)],
        [(bnd[2][0], 0), (cw, 0), (cw, ch), (bnd[2][1], ch)],
    ]
    for i, p in enumerate(polys):
        m = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(m).polygon(p, fill=255)
        m.save(BUILD / f"mask{i}.png")
    d = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    dd = ImageDraw.Draw(d)
    for tx, bx in bnd:
        dd.line([(tx, 0), (bx, ch)], fill=(255, 255, 255, 235), width=4)
    d.save(BUILD / "dividers.png")


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except Exception:
        return ImageFont.load_default()


def make_endcard(png):
    img = Image.new("RGB", (W, H), (0, 0, 0))
    dr = ImageDraw.Draw(img)
    for text, f, dy, col in [("LightCrafter", font(124), -40, (255, 255, 255)),
                             ("PBR-Conditioned Video Diffusion Refinement for Relighting", font(40), 95, (170, 180, 200))]:
        bb = dr.textbbox((0, 0), text, font=f)
        dr.text((W / 2 - (bb[2] - bb[0]) / 2, H / 2 + dy - (bb[3] - bb[1]) / 2 - bb[1]), text, fill=col, font=f)
    img.save(png)


def make_header(png, labels, panel_w, n, total_w):
    img = Image.new("RGBA", (total_w, 56), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    f = font(34)
    for i, lab in enumerate(labels):
        cx = i * panel_w + panel_w / 2
        bb = dr.textbbox((0, 0), lab, font=f)
        dr.text((cx - (bb[2] - bb[0]) / 2, 8), lab, fill=(255, 255, 255, 235), font=f)
    img.save(png)


# ---- method stage clips ----
def stage_input(src, label, out):
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", src, "-t", L,
         "-vf", FITPAD + "," + dt(label), "-an"] + ENC + [out])


def stage_pbr(src, ball, label, out):
    bw = int(CONTENT_W * 0.16)
    fc = (f"[0:v]{CSCALE}[v];[1:v]scale={bw}:-1[b];[v][b]overlay=14:14[o];"
          f"[o]{PADWH}[p];[p]{dt(label)}[out]")
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", src, "-i", ball, "-t", L,
         "-filter_complex", fc, "-map", "[out]", "-an"] + ENC + [out])


def stage_geometry(src, geo, label, out):
    cw, ch, cx, cy = geo
    vf = f"crop={cw}:{ch}:{cx}:{cy},{FITPAD},{dt(label)}"
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", src, "-t", L, "-vf", vf, "-an"] + ENC + [out])


def stage_intrinsics(d, label, out):
    chans = ["normal", "basecolor", "roughness", "metallic"]
    inp = []
    for c in chans:
        inp += ["-stream_loop", "-1", "-i", str(GAL / d / f"{c}.mp4")]
    for i in range(4):
        inp += ["-loop", "1", "-i", str(BUILD / f"mask{i}.png")]
    inp += ["-loop", "1", "-i", str(BUILD / "dividers.png")]
    parts = []
    for i in range(4):
        parts.append(f"[{i}:v]{CSCALE}[c{i}]")
        parts.append(f"[c{i}][{4+i}:v]alphamerge[a{i}]")
    parts.append(f"color=black:{CONTENT_W}x{CONTENT_H}:r={FPS}[bg]")
    parts.append("[bg][a0]overlay[o0];[o0][a1]overlay[o1];[o1][a2]overlay[o2];[o2][a3]overlay[o3]")
    parts.append(f"[o3][8:v]overlay[m];[m]{PADWH}[p];[p]{dt(label)}[out]")
    run(["ffmpeg", "-y"] + inp + ["-t", L, "-filter_complex", ";".join(parts),
         "-map", "[out]", "-an"] + ENC + [out])


def chain_xfade(clips, out, dur, transition):
    """Chain equal-length clips (each L seconds) with xfade; offsets = k*(L-dur)."""
    inp = []
    for c in clips:
        inp += ["-i", str(c)]
    step = L - dur
    parts, prev = [], "[0:v]"
    for k in range(1, len(clips)):
        off = round(k * step, 3)
        lab = "[v]" if k == len(clips) - 1 else f"[x{k}]"
        parts.append(f"{prev}[{k}:v]xfade=transition={transition}:duration={dur}:offset={off}{lab}")
        prev = lab
    fc = ";".join(parts) + ";[v]format=yuv420p[o]" if False else ";".join(parts)
    run(["ffmpeg", "-y"] + inp + ["-filter_complex", fc, "-map", "[v]", "-an"] + ENC + [out])


def build_subject(s, idx):
    d = s["dir"]
    base = GAL / d
    name = s["name"]
    clips = []
    stage_input(base / "input.mp4", f"{name}  \u2022  Input", BUILD / f"s{idx}_0.mp4"); clips.append(BUILD / f"s{idx}_0.mp4")
    stage_intrinsics(d, f"{name}  \u2022  Intrinsics Decomposition", BUILD / f"s{idx}_1.mp4"); clips.append(BUILD / f"s{idx}_1.mp4")
    stage_geometry(base / "geometry.mp4", s["geo"], f"{name}  \u2022  Geometry Reconstruction", BUILD / f"s{idx}_2.mp4"); clips.append(BUILD / f"s{idx}_2.mp4")
    stage_pbr(base / "pbr.mp4", ENV / s["ball"], f"{name}  \u2022  Relighting via PBR", BUILD / f"s{idx}_3.mp4"); clips.append(BUILD / f"s{idx}_3.mp4")
    stage_input(base / "relit.mp4", f"{name}  \u2022  Diffusion Refinement", BUILD / f"s{idx}_4.mp4"); clips.append(BUILD / f"s{idx}_4.mp4")
    chain_xfade(clips, BUILD / f"subject{idx}.mp4", WIPE, "diagtl")
    return BUILD / f"subject{idx}.mp4"


def build_wild_strip(d, idx):
    pw, ph = 600, 400          # panel size (3:2)
    total_w = pw * 3
    base = GAL / d
    # three normalized panels
    panels = []
    specs = [(base / "input.mp4", None), (base / "illum1_pbr.mp4", ENV / WILD_BALL), (base / "illum1.mp4", None)]
    for j, (src, ball) in enumerate(specs):
        outp = BUILD / f"w{idx}_{j}.mp4"
        if ball:
            bw = int(pw * 0.28)
            fc = f"[0:v]{cover(pw, ph)}[v];[1:v]scale={bw}:-1[b];[v][b]overlay=10:10[out]"
            run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src), "-i", str(ball),
                 "-t", str(WILD_L), "-filter_complex", fc, "-map", "[out]", "-an"] + ENC + [outp])
        else:
            run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src), "-t", str(WILD_L),
                 "-vf", cover(pw, ph), "-an"] + ENC + [outp])
        panels.append(outp)
    # hstack + header labels, centered on a black 1920x1080 canvas
    make_header(BUILD / f"wh{idx}.png", ["Input", "PBR", "Refinement"], pw, 3, total_w)
    inp = []
    for p in panels:
        inp += ["-i", str(p)]
    inp += ["-loop", "1", "-i", str(BUILD / f"wh{idx}.png")]
    fc = ("[0:v][1:v][2:v]hstack=inputs=3[strip];"
          f"[strip]pad={total_w}:{ph+64}:0:64:color=black[sp];"
          "[sp][3:v]overlay=0:0[lab];"
          f"[lab]pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p,setsar=1[pp];"
          f"[pp]{TITLE_DT}[out]")
    run(["ffmpeg", "-y"] + inp + ["-t", str(WILD_L), "-filter_complex", fc, "-map", "[out]", "-an"] + ENC + [BUILD / f"wild{idx}.mp4"])
    return BUILD / f"wild{idx}.mp4"


def build_wild(strips, out):
    inp = []
    for s in strips:
        inp += ["-i", str(s)]
    step = WILD_L - WILD_FADE
    parts, prev = [], "[0:v]"
    for k in range(1, len(strips)):
        off = round(k * step, 3)
        lab = "[v]" if k == len(strips) - 1 else f"[x{k}]"
        parts.append(f"{prev}[{k}:v]xfade=transition=fade:duration={WILD_FADE}:offset={off}{lab}")
        prev = lab
    run(["ffmpeg", "-y"] + inp + ["-filter_complex", ";".join(parts), "-map", "[v]", "-an"] + ENC + [out])


def dur_of(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    make_masks()

    # PART 1: method (sequential subjects)
    subj = [build_subject(s, i) for i, s in enumerate(SUBJECTS)]
    # cross-dissolve subjects
    inp = []
    for s in subj:
        inp += ["-i", str(s)]
    sl = dur_of(subj[0])
    parts, prev, cum = [], "[0:v]", sl
    for k in range(1, len(subj)):
        off = round(cum - SUBJ_FADE, 3)
        lab = "[v]" if k == len(subj) - 1 else f"[m{k}]"
        parts.append(f"{prev}[{k}:v]xfade=transition=fade:duration={SUBJ_FADE}:offset={off}{lab}")
        prev = lab
        cum = off + dur_of(subj[k])
    run(["ffmpeg", "-y"] + inp + ["-filter_complex", ";".join(parts), "-map", "[v]", "-an"] + ENC + [BUILD / "method.mp4"])

    # PART 2: in-the-wild
    strips = [build_wild_strip(d, i) for i, d in enumerate(WILD)]
    build_wild(strips, BUILD / "wild.mp4")

    # PART 3: title card (used as BOTH the 2s intro and the end card)
    make_endcard(BUILD / "card.png")
    # intro: 2s LightCrafter cover, fades in from black
    run(["ffmpeg", "-y", "-loop", "1", "-t", "2.0", "-i", str(BUILD / "card.png"),
         "-vf", f"fps={FPS},format=yuv420p,setsar=1,fade=t=in:st=0:d=0.5", "-an"] + ENC + [BUILD / "intro.mp4"])
    run(["ffmpeg", "-y", "-loop", "1", "-t", "1.8", "-i", str(BUILD / "card.png"),
         "-vf", f"fps={FPS},format=yuv420p,setsar=1", "-an"] + ENC + [BUILD / "endcard.mp4"])

    # JOIN: intro -> method -> wild -> endcard with cross-dissolves
    clips = [BUILD / "intro.mp4", BUILD / "method.mp4", BUILD / "wild.mp4", BUILD / "endcard.mp4"]
    D = 0.5
    inp = []
    for c in clips:
        inp += ["-i", str(c)]
    parts, prev, cum = [], "[0:v]", dur_of(clips[0])
    for k in range(1, len(clips)):
        off = round(cum - D, 3)
        lab = "[v]" if k == len(clips) - 1 else f"[j{k}]"
        parts.append(f"{prev}[{k}:v]xfade=transition=fade:duration={D}:offset={off}{lab}")
        prev = lab
        cum = off + dur_of(clips[k])
    fc = ";".join(parts) + ";[v]format=yuv420p[o]"
    run(["ffmpeg", "-y"] + inp + ["-filter_complex", fc, "-map", "[o]", "-an",
         "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(OUT)])
    print("DONE ->", OUT, "(", round(cum, 1), "s )")


if __name__ == "__main__":
    main()
