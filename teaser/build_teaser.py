"""
build_teaser.py — Bake the single large teaser video for the hero / Twitter.

Layout: 5 columns x 3 rows + a header band.
  Columns: Input | Intrinsics (4-way diagonal G-buffer composite) |
           Geometry | Relighting (PBR, env-ball overlay) | Refinement
  Rows:    Dancing (lalaland) | Car (car-light-insertion) | Human

All cells are normalized to CELL_W x CELL_H (3:2, cover-crop), looped to DUR
seconds at FPS, padded with a white gap, then stacked. Output: ../static/videos/teaser.mp4

Run:  python build_teaser.py     (needs ffmpeg + Pillow)
"""

import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent.parent          # website-arxiv
GAL = ROOT / "static/videos/gallery"
ENV = ROOT / "static/images/envmaps"
BUILD = Path(__file__).parent / "_teaser_build"
OUT = ROOT / "static/videos/teaser.mp4"

CELL_W, CELL_H = 384, 256
GAP = 6
FPS = 10
DUR = 10
HEADER_H = 56
O = 0.12  # diagonal slant (fraction of width)

COLS = ["Input", "Intrinsics Decomposition", "Geometry Reconstruction", "Relighting via PBR", "Diffusion Refinement"]
GEO_ZOOM = 1.7  # crop the geometry clip in to reduce white margins
# geo = (cw, ch, cx, cy): source-pixel crop window (3:2) on the 960x720 geometry
# clip for the Geometry Reconstruction cell only, before scaling to the cell.
ROWS = [
    {"dir": "lalaland",            "ball": "kiara_5_noon_2k_ball.png",          "geo": (470, 313, 330, 175)},
    {"dir": "car-light-insertion", "ball": "satara_night_no_lamps_2k_ball.png", "geo": (380, 253, 300, 315)},
    {"dir": "human",               "ball": "kiara_5_noon_2k_ball.png",          "geo": (560, 373, 340, 130)},
]

PADW, PADH = CELL_W + GAP, CELL_H + GAP   # cell incl. right/bottom gap


def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG ERROR:\n", " ".join(str(a) for a in args))
        print(r.stderr[-2000:])
        raise SystemExit(1)


def band_polys():
    W, H, o = CELL_W, CELL_H, O * CELL_W
    c = [0.25 * W, 0.5 * W, 0.75 * W]
    bnd = [(ci + o, ci - o) for ci in c]  # (top_x, bottom_x)
    polys = []
    polys.append([(0, 0), (bnd[0][0], 0), (bnd[0][1], H), (0, H)])
    polys.append([(bnd[0][0], 0), (bnd[1][0], 0), (bnd[1][1], H), (bnd[0][1], H)])
    polys.append([(bnd[1][0], 0), (bnd[2][0], 0), (bnd[2][1], H), (bnd[1][1], H)])
    polys.append([(bnd[2][0], 0), (W, 0), (W, H), (bnd[2][1], H)])
    return polys, bnd


def make_masks():
    polys, bnd = band_polys()
    for i, p in enumerate(polys):
        m = Image.new("L", (CELL_W, CELL_H), 0)
        ImageDraw.Draw(m).polygon(p, fill=255)
        m.save(BUILD / f"mask{i}.png")
    # divider overlay (transparent + 3 white diagonal lines)
    d = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(d)
    for tx, bx in bnd:
        dd.line([(tx, 0), (bx, CELL_H)], fill=(255, 255, 255, 235), width=2)
    d.save(BUILD / "dividers.png")


def load_font(size):
    for f in ["/System/Library/Fonts/Supplemental/Arial.ttf",
              "/System/Library/Fonts/Helvetica.ttc",
              "/Library/Fonts/Arial.ttf"]:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_header():
    total_w = 5 * PADW
    img = Image.new("RGB", (total_w, HEADER_H), (255, 255, 255))
    dr = ImageDraw.Draw(img)
    font = load_font(19)
    for i, label in enumerate(COLS):
        cx = i * PADW + CELL_W / 2
        bb = dr.textbbox((0, 0), label, font=font)
        w = bb[2] - bb[0]
        dr.text((cx - w / 2, (HEADER_H - (bb[3] - bb[1])) / 2 - bb[1]), label,
                fill=(40, 40, 40), font=font)
    img.save(BUILD / "header.png")


def cover_vf(zoom=1.0):
    w, h = int(CELL_W * zoom), int(CELL_H * zoom)
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={CELL_W}:{CELL_H},fps={FPS},format=yuv420p"


COVER = cover_vf(1.0)
PAD = f"pad={PADW}:{PADH}:0:0:color=white"


def cell_simple(src, out, zoom=1.0):
    vf = cover_vf(zoom) + "," + PAD
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
         "-t", str(DUR), "-vf", vf, "-an",
         "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p", str(out)])


def cell_geometry(src, out, cw, ch, cx, cy):
    vf = (f"crop={cw}:{ch}:{cx}:{cy},scale={CELL_W}:{CELL_H},"
          f"fps={FPS},format=yuv420p,{PAD}")
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
         "-t", str(DUR), "-vf", vf, "-an",
         "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p", str(out)])


def cell_pbr(src, ball, out):
    # PBR with env chrome-ball overlay in the top-left corner.
    ball_w = int(CELL_W * 0.26)
    fc = (
        f"[0:v]{COVER}[v];"
        f"[1:v]scale={ball_w}:-1[b];"
        f"[v][b]overlay=8:8[ov];"
        f"[ov]{PAD}[out]"
    )
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src), "-i", str(ball),
         "-t", str(DUR), "-filter_complex", fc, "-map", "[out]", "-an",
         "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p", str(out)])


def cell_intrinsics(d, out):
    chans = ["normal", "basecolor", "roughness", "metallic"]
    inputs = []
    for c in chans:
        inputs += ["-stream_loop", "-1", "-i", str(GAL / d / f"{c}.mp4")]
    for i in range(4):
        inputs += ["-loop", "1", "-i", str(BUILD / f"mask{i}.png")]
    inputs += ["-loop", "1", "-i", str(BUILD / "dividers.png")]
    # indices: 0-3 channels, 4-7 masks, 8 dividers
    parts = []
    for i in range(4):
        parts.append(f"[{i}:v]{COVER}[c{i}]")
        parts.append(f"[c{i}][{4+i}:v]alphamerge[a{i}]")
    parts.append(f"color=black:{CELL_W}x{CELL_H}:r={FPS}[bg]")
    parts.append("[bg][a0]overlay[o0]")
    parts.append("[o0][a1]overlay[o1]")
    parts.append("[o1][a2]overlay[o2]")
    parts.append("[o2][a3]overlay[o3]")
    parts.append("[o3][8:v]overlay[m]")
    parts.append(f"[m]{PAD}[out]")
    fc = ";".join(parts)
    run(["ffmpeg", "-y"] + inputs + ["-t", str(DUR), "-filter_complex", fc,
         "-map", "[out]", "-an", "-c:v", "libx264", "-crf", "18", "-preset", "fast",
         "-pix_fmt", "yuv420p", str(out)])


def build_row(r, d, ball, geo):
    base = GAL / d
    cells = []
    cell_simple(base / "input.mp4", BUILD / f"r{r}c0.mp4");           cells.append(BUILD / f"r{r}c0.mp4")
    cell_intrinsics(d, BUILD / f"r{r}c1.mp4");                        cells.append(BUILD / f"r{r}c1.mp4")
    cell_geometry(base / "geometry.mp4", BUILD / f"r{r}c2.mp4", geo[0], geo[1], geo[2], geo[3]); cells.append(BUILD / f"r{r}c2.mp4")
    cell_pbr(base / "pbr.mp4", ENV / ball, BUILD / f"r{r}c3.mp4");    cells.append(BUILD / f"r{r}c3.mp4")
    cell_simple(base / "relit.mp4", BUILD / f"r{r}c4.mp4");           cells.append(BUILD / f"r{r}c4.mp4")
    # hstack the 5 cells
    inputs = []
    for c in cells:
        inputs += ["-i", str(c)]
    fc = "".join(f"[{i}:v]" for i in range(5)) + "hstack=inputs=5[out]"
    run(["ffmpeg", "-y"] + inputs + ["-filter_complex", fc, "-map", "[out]", "-an",
         "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
         str(BUILD / f"row{r}.mp4")])


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    make_masks()
    make_header()
    for r, row in enumerate(ROWS):
        print(f"[row {r}] {row['dir']}")
        build_row(r, row["dir"], row["ball"], row["geo"])
    # vstack header + 3 rows
    total_w = 5 * PADW
    inputs = ["-loop", "1", "-t", str(DUR), "-i", str(BUILD / "header.png")]
    for r in range(3):
        inputs += ["-i", str(BUILD / f"row{r}.mp4")]
    fc = (f"[0:v]scale={total_w}:{HEADER_H},fps={FPS},format=yuv420p[h];"
          "[h][1:v][2:v][3:v]vstack=inputs=4[stk];"
          f"[stk]pad=iw+{GAP}:ih+{GAP}:{GAP}:{GAP}:color=white[out]")
    run(["ffmpeg", "-y"] + inputs + ["-filter_complex", fc, "-map", "[out]", "-an",
         "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(OUT)])
    print("DONE ->", OUT)


if __name__ == "__main__":
    main()
