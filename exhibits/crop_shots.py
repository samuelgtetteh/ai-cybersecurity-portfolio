"""
Prepare tidy screenshot copies for Exhibit 20:
  * dashboards: crop off the browser chrome (tab strip / address bar / bookmarks) -> clean app view
  * JSON endpoint captures: drop the tab strip (keep the address bar for URL provenance) and
    trim trailing right-hand whitespace so the JSON fills the frame

Outputs to exhibits/evidence/shots/ so the exhibit builds reproducibly from the repo.
"""
import os
from PIL import Image

SRC = r"C:\Users\User\Pictures\Screenshots"
OUT = os.path.join(os.path.dirname(__file__), "evidence", "shots")
os.makedirs(OUT, exist_ok=True)

DASH_CHROME = 118   # px of browser chrome above the RegMap app
TAB_STRIP = 34      # px of tab strip above the address bar on the JSON captures

JOBS = [
    ("Screenshot 2026-07-17 103148.png", "fig1_monitor_1031.png", "dash"),
    ("Screenshot 2026-07-17 103231.png", "fig2_monitor_1032.png", "dash"),
    ("Screenshot 2026-07-17 103748.png", "fig3_stats.png", "json"),
    ("Screenshot 2026-07-17 103820.png", "fig4_metrics_all.png", "json"),
    ("Screenshot 2026-07-17 103850.png", "fig5_metrics_identity.png", "json"),
    ("Screenshot 2026-07-17 103915.png", "fig6_metrics_ics.png", "json"),
]


ADDR_H = 38     # address-bar height on a tab-stripped capture
JSON_TOP = 104  # y where the JSON body begins (below address + bookmarks + pretty-print bars)


def right_trim(img, pad=12, thresh=248):
    """Crop trailing near-white columns on the right so content fills the width."""
    g = img.convert("L")
    w, h = g.size
    px = g.load()
    last = 0
    for x in range(w):
        if any(px[x, y] < thresh for y in range(0, h, 3)):
            last = x
    return img.crop((0, 0, min(w, last + pad), h))


def json_composite(im):
    """Stack the address bar (URL provenance) directly above the JSON body, dropping the
    personal bookmarks bar and the pretty-print row in between."""
    w, h = im.size
    addr = im.crop((0, 0, w, ADDR_H))
    body = im.crop((0, JSON_TOP, w, h))
    gap = 6
    out = Image.new("RGB", (w, ADDR_H + gap + body.size[1]), "white")
    out.paste(addr, (0, 0))
    out.paste(body, (0, ADDR_H + gap))
    return out


for src, dst, kind in JOBS:
    im = Image.open(os.path.join(SRC, src)).convert("RGB")
    w, h = im.size
    if kind == "dash":
        im = im.crop((0, DASH_CHROME, w, h))
    else:
        im = im.crop((0, TAB_STRIP, w, h))
        im = json_composite(im)
        im = right_trim(im)
    im.save(os.path.join(OUT, dst))
    print(dst, im.size)
