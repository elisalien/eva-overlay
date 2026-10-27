#!/usr/bin/env python3
"""Drive banc.html in Chrome (GPU) to take stills or render a frame sequence.

  python shoot.py stills 1080 1920          -> shots/<w>x<h>_p<N>.png, one per preset
  python shoot.py reel                      -> frames/00000.png ... from reel.json, then ffmpeg

The bench is served by a local http.server started here (port 8834).
"""
import base64
import http.server
import json
import socketserver
import sys
import threading
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PORT = 8834


def serve():
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE))
    handler.log_message = lambda *a: None
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def open_bench(p, w, h):
    browser = p.chromium.launch(channel="chrome", headless=False,
                                args=["--use-angle=gl", "--enable-gpu", "--ignore-gpu-blocklist",
                                      "--window-position=-2400,0", "--window-size=400,300"])
    page = browser.new_page()
    page.set_default_timeout(120000)
    page.goto(f"http://127.0.0.1:{PORT}/banc.html?wait=1&t=0&w={w}&h={h}")
    page.evaluate("window.load()")
    page.on("console", lambda m: print("console:", m.text[:300], flush=True))
    import time
    for _ in range(240):
        st = page.evaluate("[String(window.isfError), window.compileMs, !!window.values]")
        if st[2] or (st[0] not in ("waiting", "loading", "undefined", "")):
            break
        time.sleep(0.5)
    print("bench:", st, flush=True)
    err = page.evaluate("window.isfError")
    if err:
        raise SystemExit(err)
    return browser, page


def grab(page, path):
    data = page.evaluate("window.cv.toDataURL('image/png')")
    Path(path).write_bytes(base64.b64decode(data.split(",", 1)[1]))


SET_FIELDS = """(texts) => { texts.forEach((t, k) => { if (t !== null && FIELDS[k].text !== t) { FIELDS[k].text = t; renderField(k); } }); }"""


def stills(w, h):
    out = HERE / "shots"
    out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser, page = open_bench(p, w, h)
        page.evaluate("window.values.transDur = 0")
        t = 0.0
        for pr in range(9):
            page.evaluate(f"window.values.preset = {pr}")
            page.evaluate(f"play({t:.4f}, {t + 3.5:.4f}, 30)")
            t += 3.6
            grab(page, out / f"{w}x{h}_p{pr}.png")
            print("preset", pr, flush=True)
        browser.close()


def reel(spec_name="reel.json"):
    """Plays reel.json in one bench session at the reel size. A "split" segment is also
    rendered at 16:9, 1:1 and 9:16 in separate sessions and composited over its frames."""
    spec = json.loads((HERE / spec_name).read_text(encoding="utf-8"))
    w, h, fps = spec["w"], spec["h"], spec["fps"]
    out = HERE / spec.get("frames", "frames")
    out.mkdir(exist_ok=True)
    for f in out.glob("*.png"):
        f.unlink()
    splits = []
    with sync_playwright() as p:
        browser, page = open_bench(p, w, h)
        n, t, prev = 0, 0.0, None
        for seg in spec["segments"]:
            vals = dict(spec.get("defaults", {}))
            vals.update(seg.get("values", {}))
            page.evaluate("(v) => Object.assign(window.values, v)", vals)
            # Texts change at the cut (half the transition), so the outgoing preset leaves
            # with its own words.
            delay = 0.0 if prev in (None, vals["preset"]) else vals["transDur"] * 0.5
            frames = int(round(seg["dur"] * fps))
            if seg.get("split"):
                splits.append((n, frames, seg, vals))
            for k in range(frames):
                if abs(k / fps - delay) < 0.5 / fps or (k == 0 and delay == 0.0):
                    page.evaluate(SET_FIELDS, seg["texts"])
                page.evaluate(f"draw({t:.5f})")
                grab(page, out / f"{n:05d}.png")
                n += 1
                t += 1.0 / fps
            prev = vals["preset"]
            print(seg["name"], n, flush=True)
        browser.close()
        for n0, frames, seg, vals in splits:
            for (sw, sh) in [(1920, 1080), (1080, 1080), (1080, 1920)]:
                d = HERE / "split" / f"{sw}x{sh}"
                d.mkdir(parents=True, exist_ok=True)
                browser, page = open_bench(p, sw, sh)
                page.evaluate("(v) => Object.assign(window.values, v)", vals)
                page.evaluate(SET_FIELDS, seg["texts"])
                for k in range(frames):
                    page.evaluate(f"draw({k / fps:.5f})")
                    grab(page, d / f"{k:05d}.png")
                browser.close()
                print("split", sw, sh, flush=True)
            compose_split(n0, frames, out, spec.get("captions"))
    encode(out, HERE / spec.get("out", "reel.mp4"), fps)
    import shutil
    shutil.rmtree(out, ignore_errors=True)
    shutil.rmtree(HERE / "split", ignore_errors=True)


def encode(frames, mp4, fps):
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames / "%05d.png"),
                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
                    "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "17",
                    "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(mp4)], check=True)
    print("->", mp4, flush=True)


DEFAULT_CAPTIONS = [["MÊME PATCH  ·  3 FORMATS", 40, 90, "ui", "org"],
                    ["la mise en page se recompose seule", 40, 1680, "mincho", "white"],
                    ["16:9 · 1:1 · 9:16 · ultra-large", 40, 1760, "small", "org"]]


def compose_split(n0, frames, out, captions=None):
    from PIL import Image, ImageDraw, ImageFont
    org = (255, 120, 10)
    ui = ImageFont.truetype("C:/Windows/Fonts/bahnschrift.ttf", 64)
    ui.set_variation_by_name("Bold Condensed")
    small = ImageFont.truetype("C:/Windows/Fonts/bahnschrift.ttf", 34)
    small.set_variation_by_name("Bold Condensed")
    mincho = ImageFont.truetype(str(HERE / "fonts/ShipporiMinchoB1-ExtraBold.ttf"), 52)
    boxes = [("16:9", (1920, 1080), (0, 250, 1080, 608)),
             ("1:1", (1080, 1080), (24, 960, 640, 640)),
             ("9:16", (1080, 1920), (696, 960, 360, 640))]
    for k in range(frames):
        cv = Image.new("RGB", (1080, 1920), (0, 0, 0))
        d = ImageDraw.Draw(cv)
        fonts = {"ui": ui, "small": small, "mincho": mincho}
        cols = {"org": org, "white": (255, 255, 255)}
        for text, x, y, f, c in captions or DEFAULT_CAPTIONS:
            d.text((x, y), text, font=fonts[f], fill=cols[c])
        d.line((40, 200, 1040, 200), fill=org, width=3)
        for label, (sw, sh), (x, y, bw, bh) in boxes:
            im = Image.open(HERE / "split" / f"{sw}x{sh}" / f"{k:05d}.png").convert("RGBA")
            bg = Image.new("RGBA", im.size, (0, 0, 0, 255))
            bg.alpha_composite(im)
            cv.paste(bg.convert("RGB").resize((bw, bh), Image.LANCZOS), (x, y))
            d.rectangle((x - 2, y - 2, x + bw + 1, y + bh + 1), outline=org, width=3)
            d.rectangle((x - 2, y - 46, x + 110, y - 4), fill=org)
            d.text((x + 10, y - 44), label, font=small, fill=(0, 0, 0))
        cv.save(out / f"{n0 + k:05d}.png")


if __name__ == "__main__":
    httpd = serve()
    if sys.argv[1] == "stills":
        stills(int(sys.argv[2]), int(sys.argv[3]))
    else:
        reel(sys.argv[2] if len(sys.argv) > 2 else "reel.json")
    httpd.shutdown()
