#!/usr/bin/env python3
"""Make an animated email signature from a JSON config.

    python3 scripts/make_signature.py my-signature.json
    python3 scripts/make_signature.py my-signature.json --gif-url https://example.com/signature.gif --html-only

Writes into the output folder (default: an "output" folder next to the config):
    signature.gif         the animated card, 1040x392 (shown at 520x196)
    signature-static.png  the first frame, for places that don't play GIFs
    signature.html        the snippet to paste into Gmail (needs --gif-url or "gif_url" in the config)
    preview.html          the signature under a sample email, light and dark, with the local GIF

Needs Python 3.9+, Playwright with Chromium, ffmpeg and gifsicle.
"""
import argparse
import base64
import html
import json
import mimetypes
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARD = ROOT / "template" / "card.html"
SNIPPET = ROOT / "template" / "signature.html"
WIDTH, HEIGHT, SCALE = 520, 196, 2
PLACEHOLDER_URL = "https://YOUR-SITE.com/signature.gif"

DEFAULT_SECONDS = {"typing": 2.55, "list": 2.55, "statement": 2.4, "image": 2.4}
LIGHT_PANEL = {"panel": "#FBFAF7", "ink": "#1A1410", "ink2": "#3A3330", "ink3": "#9A928A", "num": "#8A8178",
               "hair": "#E4DED6", "rule": "#ECE7E0", "bubble": "#EFEBE6"}


def die(msg):
    sys.exit("error: " + msg)


def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        die(f"'{h}' is not a hex colour like #FF6B35")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, w):
    """Colour a moved a share w of the way to colour b."""
    ra, rb = hex_rgb(a), hex_rgb(b)
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * w) for x, y in zip(ra, rb))


def luminance(h):
    r, g, b = (c / 255 for c in hex_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def colours(cfg):
    given = dict(cfg.get("colors") or cfg.get("colours") or {})
    bg = given.pop("background", None) or given.get("card") or "#111111"
    accent = given.get("accent") or "#FF6B35"
    text = given.get("text") or ("#FCFCF8" if luminance(bg) < 0.5 else "#141414")
    out = {
        "card": bg, "accent": accent, "text": text,
        "border": mix(bg, text, 0.14), "chip": mix(bg, text, 0.05), "chip-border": mix(bg, text, 0.2),
        "label": mix(text, bg, 0.08), "muted": mix(text, bg, 0.3), "faint": mix(text, bg, 0.62),
        "statement": mix(bg, text, 0.045),
    }
    out.update(LIGHT_PANEL)
    out.update(given)  # anything set by hand wins
    return out


def data_uri(path):
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if path.suffix.lower() == ".svg":
        mime = "image/svg+xml"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def load_config(path):
    try:
        cfg = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON: {e}")
    for key in ("name", "company"):
        if not cfg.get(key):
            die(f"the config needs \"{key}\"")
    base = path.parent

    def asset(value):
        p = (base / value).resolve()
        if not p.exists():
            die(f"can't find {value} (looked in {base})")
        return data_uri(p)

    slides = cfg.get("slides")
    if not slides:
        lines = cfg.get("lines") or []
        if not lines:
            die("the config needs \"lines\" (a list of short sentences) or \"slides\"")
        slides = [{"type": "statement", "text": line, "big": True} for line in lines]
    for i, s in enumerate(slides):
        kind = s.get("type", "statement")
        if kind not in DEFAULT_SECONDS:
            die(f"slide {i + 1} has type \"{kind}\"; use typing, list, statement or image")
        s["type"] = kind
        s.setdefault("seconds", DEFAULT_SECONDS[kind])
        if kind == "image":
            s["src"] = asset(s["src"])
    card = {
        "company": cfg["company"],
        "label": cfg.get("label", ""),
        "label_icon": cfg.get("label_icon", "search"),
        "headline": cfg.get("headline", ""),
        "colors": colours(cfg),
        "slides": slides,
        "start_with_last": cfg.get("start_with_last", True),
    }
    if card["label_icon"] not in ("search", "check", "spark", "mail", "none"):
        card["label_icon"] = asset(card["label_icon"])
    if cfg.get("logo"):
        card["logo"] = asset(cfg["logo"])
    if cfg.get("statement_logo"):
        card["statement_logo"] = asset(cfg["statement_logo"])
    return cfg, card


def plain(text):
    return re.sub(r"\s+", " ", text.replace("*", "")).strip()


def write_html(cfg, out, gif_url):
    title = " &middot; ".join(html.escape(x.upper()) for x in (cfg.get("title", ""), cfg["company"]) if x)
    last = cfg.get("slides", [{}])[-1].get("text") if cfg.get("slides") else (cfg.get("lines") or [""])[-1]
    alt = cfg.get("alt") or (f"{cfg['company']}: {plain(last)}" if last else cfg["company"])
    link = cfg.get("link", "")
    if link and not re.match(r"https?://", link):
        link = "https://" + link
    fill = {
        "NAME": html.escape(cfg["name"]), "TITLE_LINE": title, "ALT": html.escape(alt, quote=True),
        "LINK_OPEN": f'<a href="{html.escape(link, quote=True)}" target="_blank" style="text-decoration:none;border:0;">' if link else "",
        "LINK_CLOSE": "</a>" if link else "",
    }
    snippet = SNIPPET.read_text()
    for k, v in fill.items():
        snippet = snippet.replace("{{" + k + "}}", v)
    (out / "signature.html").write_text(snippet.replace("{{GIF_URL}}", html.escape(gif_url or PLACEHOLDER_URL, quote=True)))
    local = snippet.replace("{{GIF_URL}}", "signature.gif")
    dark = local.replace("color:#222222", "color:#E3E3E3")
    first = html.escape(cfg["name"].split()[0])
    body = f"Hi Sam,<br><br>Thursday at 2 works. I'll send the invite.<br><br>{first}"
    (out / "preview.html").write_text(f"""<!doctype html><html><head><meta charset="utf-8"><title>Signature preview</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:#F1F3F4}}
.mail{{max-width:600px;margin:24px auto;padding:24px 28px;border-radius:12px;font-size:14px;line-height:20px}}
.light{{background:#fff;color:#1F1F1F}} .dark{{background:#1F1F1F;color:#E3E3E3}}
h1{{max-width:600px;margin:24px auto 0;font-size:13px;font-weight:normal;color:#5E5E5E;padding:0 4px}}
</style></head><body>
<h1>Light</h1><div class="mail light">{body}{local}</div>
<h1>Dark</h1><div class="mail dark">{body}{dark}</div>
</body></html>""")


def check_tools():
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        die("Playwright is missing. Run: pip install playwright && python3 -m playwright install chromium")
    for tool in ("ffmpeg", "gifsicle"):
        if not shutil.which(tool):
            die(f"{tool} is missing. macOS: brew install {tool}. Ubuntu: sudo apt install {tool}")


def render_frames(card, frames_dir, fps):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--allow-file-access-from-files"])
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=SCALE)
        page.goto(CARD.as_uri())
        duration = page.evaluate("c => build(c)", card)
        page.evaluate("""async () => { await Promise.all([document.fonts.load('400 12px Geist'),
            document.fonts.load('400 12px GeistMono'), document.fonts.load('800 12px Archivo')]); await document.fonts.ready; }""")
        warnings = page.evaluate("overflow()")
        count = int(round(duration * fps))
        for i in range(count):
            page.evaluate(f"render({i / fps})")
            page.locator("#card").screenshot(path=str(frames_dir / f"f{i:04d}.png"), omit_background=True)
        browser.close()
    return duration, count, warnings


def make_gif(frames_dir, fps, gif):
    raw = frames_dir / "raw.gif"
    # One 128-colour palette for the whole loop. ffmpeg stores only the part of each frame that changed.
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", str(frames_dir / "f%04d.png"),
                    "-filter_complex", "split[a][b];[a]palettegen=max_colors=128:reserve_transparent=1:stats_mode=full[p];"
                    "[b][p]paletteuse=dither=sierra2_4a:alpha_threshold=128:diff_mode=rectangle",
                    "-loop", "0", str(raw)], check=True)
    # -O3 also merges identical frames in a row into one longer frame, which keeps the file small.
    subprocess.run(["gifsicle", "--no-warnings", "-O3", "--colors", "128", str(raw), "-o", str(gif)], check=True)


def main():
    ap = argparse.ArgumentParser(description="Make an animated email signature from a JSON config.")
    ap.add_argument("config", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, help="output folder (default: 'output' next to the config)")
    ap.add_argument("--gif-url", help="the public https link where signature.gif will live")
    ap.add_argument("--html-only", action="store_true", help="only rewrite signature.html and preview.html")
    ap.add_argument("--fps", type=int, default=20)
    a = ap.parse_args()
    cfg, card = load_config(a.config)
    out = (a.out or a.config.parent / "output").resolve()
    out.mkdir(parents=True, exist_ok=True)
    gif_url = a.gif_url or cfg.get("gif_url", "")
    if gif_url and not gif_url.startswith("https://"):
        die("the GIF link must start with https://")
    write_html(cfg, out, gif_url)
    if not a.html_only:
        check_tools()
        with tempfile.TemporaryDirectory() as tmp:
            frames = pathlib.Path(tmp)
            duration, count, warnings = render_frames(card, frames, a.fps)
            make_gif(frames, a.fps, out / "signature.gif")
            shutil.copyfile(frames / "f0000.png", out / "signature-static.png")
        size = (out / "signature.gif").stat().st_size
        print(f"signature.gif         {size / 1024:.0f} KB, {duration:.2f} s loop, {WIDTH * SCALE}x{HEIGHT * SCALE}")
        print("signature-static.png  the first frame")
        if size > 1024 * 1024:
            print("note: the GIF is over 1 MB. Fewer or simpler slides make it smaller.")
        for w in warnings:
            print("warning:", w)
    print("preview.html          open it to check the signature in light and dark")
    if gif_url:
        print(f"signature.html        ready to paste, using {gif_url}")
    else:
        print("signature.html        has a placeholder link. Upload signature.gif, then run again with --gif-url <link> --html-only")
    print(f"folder: {out}")


if __name__ == "__main__":
    main()
