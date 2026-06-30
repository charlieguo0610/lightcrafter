"""
build_hero_teaser.py — Short teaser following "one example -> many examples".

  PART 1  HERO (~5s): the CAR as a single pipeline strip, shown all at once:
          Input | Intrinsics | Geometry | Relighting via PBR | Refinement (labeled).
          One fade-in, no choppy cuts -> the viewer reads the whole method at a glance.
  PART 2  MANY (~6s): a 3x3 grid of results (lalaland, human, + in-the-wild) shown all
          at once; a single diagonal sweep relights the entire grid (Input -> Relit).

No intro title card. Minimal transitions. ~11s total.

Run:  python build_hero_teaser.py     (needs ffmpeg + Pillow)
Output: ../static/videos/teaser.mp4
"""

import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent.parent
GAL = ROOT / "static/videos/gallery"
ENV = ROOT / "static/images/envmaps"
BUILD = Path(__file__).parent / "_hero_build"
OUT = ROOT / "static/videos/teaser.mp4"

W, H = 1920, 1080
FPS = 30
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
ENC = ["-r", str(FPS), "-c:v", "libx264", "-crf", "18", "-preset", "fast",
       "-pix_fmt", "yuv420p", "-video_track_timescale", str(FPS * 512)]

# Hero pipeline strip
PW, PH = 372, 248                 # panel size (3:2)
HERO_LABELS = ["Input", "Intrinsics", "Geometry", "Relighting via PBR", "Refinement"]
HERO_DUR = 5.0
CAR = {"dir": "car-light-insertion", "ball": "satara_night_no_lamps_2k_ball.png", "geo": (380, 253, 300, 315)}

# In-the-wild: each example is a ROW = Input | PBR (round env-ball) | Refinement.
# 3 examples per page; pages cross-dissolve.
CW2, CH2 = 480, 320               # row cell (3:2)
HDR = 100                         # page header height (title + column labels)
PAGE_HOLD = 3.4
EXAMPLES = [
    {"dir": "lalaland",                              "pbr": "pbr.mp4",       "relit": "relit.mp4", "ball": "kiara_5_noon_2k_ball.png"},
    {"dir": "human",                                 "pbr": "pbr.mp4",       "relit": "relit.mp4", "ball": "kiara_5_noon_2k_ball.png"},
    {"dir": "in-the-wild-scene-paper/scene_1",       "pbr": "illum1_pbr.mp4", "relit": "illum1.mp4", "ball": "autumn_field_puresky_2k_ball.png"},
    {"dir": "in-the-wild-scene-paper/scene_7",       "pbr": "illum1_pbr.mp4", "relit": "illum1.mp4", "ball": "autumn_field_puresky_2k_ball.png"},
    {"dir": "in-the-wild-scene-paper/europe_building", "pbr": "illum1_pbr.mp4", "relit": "illum1.mp4", "ball": "autumn_field_puresky_2k_ball.png"},
    {"dir": "in-the-wild-scene-paper/temple",        "pbr": "illum1_pbr.mp4", "relit": "illum1.mp4", "ball": "autumn_field_puresky_2k_ball.png"},
]


def run(args):
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG ERROR:\n", " ".join(str(a) for a in args))
        print(r.stderr[-2500:])
        raise SystemExit(1)


def cover(w, h):
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},format=yuv420p,setsar=1"


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def make_masks(w, h):
    o = 0.12 * w
    c = [0.25 * w, 0.5 * w, 0.75 * w]
    b = [(ci + o, ci - o) for ci in c]
    polys = [
        [(0, 0), (b[0][0], 0), (b[0][1], h), (0, h)],
        [(b[0][0], 0), (b[1][0], 0), (b[1][1], h), (b[0][1], h)],
        [(b[1][0], 0), (b[2][0], 0), (b[2][1], h), (b[1][1], h)],
        [(b[2][0], 0), (w, 0), (w, h), (b[2][1], h)],
    ]
    for i, p in enumerate(polys):
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).polygon(p, fill=255)
        m.save(BUILD / f"mask{i}.png")
    d = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(d)
    for tx, bx in b:
        dd.line([(tx, 0), (bx, h)], fill=(255, 255, 255, 235), width=2)
    d.save(BUILD / "dividers.png")


def cell_simple(src, out, w, h, dur):
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src), "-t", str(dur),
         "-vf", cover(w, h), "-an"] + ENC + [out])


def cell_pbr(src, ball, out, w, h, dur):
    bw = int(w * 0.26)
    fc = f"[0:v]{cover(w, h)}[v];[1:v]scale={bw}:-1[b];[v][b]overlay=8:8[out]"
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src), "-i", str(ball), "-t", str(dur),
         "-filter_complex", fc, "-map", "[out]", "-an"] + ENC + [out])


def cell_geometry(src, geo, out, w, h, dur):
    cw, ch, cx, cy = geo
    vf = f"crop={cw}:{ch}:{cx}:{cy},{cover(w, h)}"
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src), "-t", str(dur),
         "-vf", vf, "-an"] + ENC + [out])


def cell_intrinsics(d, out, w, h, dur):
    chans = ["normal", "basecolor", "roughness", "metallic"]
    inp = []
    for c in chans:
        inp += ["-stream_loop", "-1", "-i", str(GAL / d / f"{c}.mp4")]
    for i in range(4):
        inp += ["-loop", "1", "-i", str(BUILD / f"mask{i}.png")]
    inp += ["-loop", "1", "-i", str(BUILD / "dividers.png")]
    parts = []
    for i in range(4):
        parts.append(f"[{i}:v]{cover(w, h)}[c{i}]")
        parts.append(f"[c{i}][{4+i}:v]alphamerge[a{i}]")
    parts.append(f"color=black:{w}x{h}:r={FPS}[bg]")
    parts.append("[bg][a0]overlay[o0];[o0][a1]overlay[o1];[o1][a2]overlay[o2];[o2][a3]overlay[o3]")
    parts.append("[o3][8:v]overlay[out]")
    run(["ffmpeg", "-y"] + inp + ["-t", str(dur), "-filter_complex", ";".join(parts),
         "-map", "[out]", "-an"] + ENC + [out])


def hero_header(png, strip_w, gap):
    """Title + 5 column labels, width = strip_w, placed above the strip."""
    img = Image.new("RGBA", (strip_w, 120), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    tf, lf = font(46), font(30)
    title = "From one video, LightCrafter relights via a PBR proxy"
    bb = dr.textbbox((0, 0), title, font=tf)
    dr.text((strip_w / 2 - (bb[2] - bb[0]) / 2, 6), title, fill=(255, 255, 255), font=tf)
    for i, lab in enumerate(HERO_LABELS):
        cx = i * (PW + gap) + PW / 2
        bb = dr.textbbox((0, 0), lab, font=lf)
        dr.text((cx - (bb[2] - bb[0]) / 2, 78), lab, fill=(210, 215, 230), font=lf)
    img.save(png)


def page_header(png):
    """Section title + 3 column labels (Input | PBR | Refinement), width = 3*CW2."""
    pw = 3 * CW2
    img = Image.new("RGBA", (pw, HDR), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    tf, lf = font(46), font(30)
    title = "In-the-Wild Relighting"
    bb = dr.textbbox((0, 0), title, font=tf)
    dr.text((pw / 2 - (bb[2] - bb[0]) / 2, 4), title, fill=(255, 255, 255), font=tf)
    for i, lab in enumerate(["Input", "PBR", "Refinement"]):
        cx = i * CW2 + CW2 / 2
        bb = dr.textbbox((0, 0), lab, font=lf)
        dr.text((cx - (bb[2] - bb[0]) / 2, 60), lab, fill=(210, 215, 230), font=lf)
    img.save(png)


def build_hero():
    d = CAR["dir"]
    base = GAL / d
    make_masks(PW, PH)
    cells = []
    cell_simple(base / "input.mp4", BUILD / "h0.mp4", PW, PH, HERO_DUR); cells.append(BUILD / "h0.mp4")
    cell_intrinsics(d, BUILD / "h1.mp4", PW, PH, HERO_DUR); cells.append(BUILD / "h1.mp4")
    cell_geometry(base / "geometry.mp4", CAR["geo"], BUILD / "h2.mp4", PW, PH, HERO_DUR); cells.append(BUILD / "h2.mp4")
    cell_pbr(base / "pbr.mp4", ENV / CAR["ball"], BUILD / "h3.mp4", PW, PH, HERO_DUR); cells.append(BUILD / "h3.mp4")
    cell_simple(base / "relit.mp4", BUILD / "h4.mp4", PW, PH, HERO_DUR); cells.append(BUILD / "h4.mp4")
    gap = 8
    strip_w = 5 * PW + 4 * gap
    hero_header(BUILD / "hero_hdr.png", strip_w, gap)
    inp = []
    for c in cells:
        inp += ["-i", str(c)]
    inp += ["-loop", "1", "-i", str(BUILD / "hero_hdr.png")]
    # hstack with gaps: pad each cell on the right by `gap`, then hstack, then drop trailing gap
    fc = ""
    for i in range(5):
        fc += f"[{i}:v]pad={PW+gap}:{PH}:0:0:color=black[p{i}];"
    fc += "".join(f"[p{i}]" for i in range(5)) + "hstack=inputs=5[strip0];"
    fc += f"[strip0]crop={strip_w}:{PH}:0:0[strip];"           # remove trailing gap
    fc += f"[strip]pad={strip_w}:{PH+128}:0:128:color=black[withhdr0];"
    fc += "[withhdr0][5:v]overlay=0:0[withhdr];"
    fc += (f"[withhdr]pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p,setsar=1[c];"
           "[c]fade=t=in:st=0:d=0.5[v]")
    run(["ffmpeg", "-y"] + inp + ["-t", str(HERO_DUR), "-filter_complex", fc, "-map", "[v]", "-an"] + ENC + [BUILD / "hero.mp4"])


def build_example_row(ex, out):
    """One row: Input | PBR (+ round env-ball) | Refinement, each CW2 x CH2."""
    base = GAL / ex["dir"]
    bw = int(CW2 * 0.26)
    fc = (f"[0:v]{cover(CW2, CH2)}[i];"
          f"[1:v]{cover(CW2, CH2)}[p0];[3:v]scale={bw}:-1[b];[p0][b]overlay=6:6[p];"
          f"[2:v]{cover(CW2, CH2)}[r];"
          "[i][p][r]hstack=inputs=3[out]")
    run(["ffmpeg", "-y",
         "-stream_loop", "-1", "-i", str(base / "input.mp4"),
         "-stream_loop", "-1", "-i", str(base / ex["pbr"]),
         "-stream_loop", "-1", "-i", str(base / ex["relit"]),
         "-loop", "1", "-i", str(ENV / ex["ball"]),
         "-t", str(PAGE_HOLD), "-filter_complex", fc, "-map", "[out]", "-an"] + ENC + [out])


def build_page(exs, out):
    rows = []
    for j, ex in enumerate(exs):
        rp = BUILD / f"row_{out.stem}_{j}.mp4"
        build_example_row(ex, rp)
        rows.append(rp)
    pw = 3 * CW2
    inp = []
    for r in rows:
        inp += ["-i", str(r)]
    inp += ["-loop", "1", "-i", str(BUILD / "page_hdr.png")]
    n = len(rows)
    fc = ("".join(f"[{i}:v]" for i in range(n)) + f"vstack=inputs={n}[rows];"
          f"[rows]pad={pw}:{n*CH2+HDR}:0:{HDR}:color=black[pp];"
          f"[pp][{n}:v]overlay=0:0[lab];"
          f"[lab]pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p,setsar=1[out]")
    run(["ffmpeg", "-y"] + inp + ["-t", str(PAGE_HOLD), "-filter_complex", fc, "-map", "[out]", "-an"] + ENC + [out])


def build_pages():
    page_header(BUILD / "page_hdr.png")
    pages = []
    for p in range(0, len(EXAMPLES), 3):
        exs = EXAMPLES[p:p + 3]
        op = BUILD / f"page{p//3}.mp4"
        build_page(exs, op)
        pages.append(op)
    return pages


def dur_of(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    build_hero()
    pages = build_pages()

    clips = [BUILD / "hero.mp4"] + pages
    D = 0.6
    inp = []
    for c in clips:
        inp += ["-i", str(c)]
    parts, prev, cum = [], "[0:v]", dur_of(clips[0])
    for k in range(1, len(clips)):
        off = round(cum - D, 3)
        lab = f"[j{k}]"
        parts.append(f"{prev}[{k}:v]xfade=transition=fade:duration={D}:offset={off}{lab}")
        prev = lab
        cum = off + dur_of(clips[k])
    total = cum
    parts.append(f"{prev}fade=t=out:st={round(total-0.5,3)}:d=0.5,format=yuv420p[v]")
    fc = ";".join(parts)
    run(["ffmpeg", "-y"] + inp + ["-filter_complex", fc, "-map", "[v]", "-an",
         "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(OUT)])
    print("DONE ->", OUT, "(", round(total, 1), "s )")


if __name__ == "__main__":
    main()
