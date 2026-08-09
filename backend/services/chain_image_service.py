"""
Render a live on-chain stat card for Pepecoin.

The metrics (hashrate, difficulty, block height, peers) are in different units,
so they are shown as separate hero numbers rather than plotted together on a
shared axis. Rendering happens locally with Pillow so the numbers are not handed
to a third-party chart service.
"""

from io import BytesIO
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont

from services.crypto_service import format_hashrate

# Dark surface with ink tokens; the accent is reserved for the headline value.
SURFACE = (15, 17, 21)
PANEL = (24, 27, 33)
INK_PRIMARY = (242, 244, 247)
INK_MUTED = (154, 164, 178)
ACCENT = (61, 220, 132)

CARD_W = 1000
CARD_H = 560


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """
    Load a scalable font, preferring a real DejaVu face when present.

    python:3.11-slim ships no fonts, so Pillow's bundled default is the
    fallback. Both are scalable, so layout maths stay the same.
    """
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, ValueError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 has no scalable default
        return ImageFont.load_default()


def _fit_font(draw: ImageDraw.ImageDraw, text: str, max_w: int, size: int, bold: bool = True):
    """Step the font down until the text fits the available width."""
    while size > 18:
        font = _font(size, bold=bold)
        if draw.textlength(text, font=font) <= max_w:
            return font
        size -= 2
    return _font(18, bold=bold)


def _source_label(chain: dict[str, Any]) -> str:
    """
    Name the hosts the data actually came from.

    The snapshot may be stitched from an explorer plus peppool.space, so the
    card must not claim a single fixed source.
    """
    raw = chain.get("source") or ""
    hosts = [
        part.split("://")[-1].strip("/")
        for part in raw.split("+")
        if part.strip()
    ]
    return " · ".join(hosts) if hosts else "on-chain"


def _fmt_int(value: Optional[float]) -> str:
    return f"{int(value):,}" if value is not None else "n/a"


def _fmt_supply(value: Optional[float]) -> str:
    """Circulating supply reads better in billions than as 12 digits."""
    if value is None:
        return "n/a"
    if value >= 1e9:
        return f"{value / 1e9:.2f}B PEP"
    if value >= 1e6:
        return f"{value / 1e6:.2f}M PEP"
    return f"{value:,.0f} PEP"


def render_chain_stats_card(chain: dict[str, Any]) -> Optional[bytes]:
    """Render the on-chain snapshot as a PNG stat card. Returns None if empty."""
    if not chain:
        return None

    img = Image.new("RGB", (CARD_W, CARD_H), SURFACE)
    draw = ImageDraw.Draw(img)

    f_label = _font(26)
    f_title = _font(34, bold=True)
    f_foot = _font(22)

    draw.text((56, 44), "PEPECOIN NETWORK", font=f_title, fill=INK_PRIMARY)
    draw.text((56, 92), f"Live on-chain data · {_source_label(chain)}", font=f_label, fill=INK_MUTED)

    # Headline metric: network hashrate.
    # Hashrate only comes from the iquidus explorers. When those are blocked,
    # block height leads instead, so the card never headlines an "n/a".
    if chain.get("hashrate_ths") is not None:
        hero_label, hero = "NETWORK HASHRATE", format_hashrate(chain["hashrate_ths"])
    else:
        hero_label, hero = "BLOCK HEIGHT", _fmt_int(chain.get("block_height"))

    draw.text((56, 168), hero_label, font=f_label, fill=INK_MUTED)
    draw.text((56, 204), hero, font=_fit_font(draw, hero, CARD_W - 112, 96), fill=ACCENT)

    # Supporting metrics, each in its own unit — deliberately not co-plotted.
    block_time = chain.get("avg_block_time_s")
    stats = [
        ("DIFFICULTY", _fmt_int(chain.get("difficulty"))),
        ("BLOCK TIME", f"{block_time:.0f}s" if block_time else "n/a"),
    ]
    # Whichever metric is not already the headline fills the remaining tiles.
    if hero_label == "BLOCK HEIGHT":
        stats.append(("PEERS", _fmt_int(chain.get("connection_count"))))
    else:
        stats.insert(0, ("BLOCK HEIGHT", _fmt_int(chain.get("block_height"))))
    stats.append(("SUPPLY", _fmt_supply(chain.get("supply"))))

    margin, gap, box_h, top = 56, 16, 132, 350
    pad = 20
    # Derive the box width from the margins so the row stays symmetric.
    box_w = (CARD_W - 2 * margin - gap * (len(stats) - 1)) // len(stats)

    for i, (label, value) in enumerate(stats):
        x = margin + i * (box_w + gap)
        draw.rounded_rectangle([x, top, x + box_w, top + box_h], radius=10, fill=PANEL)
        inner_w = box_w - 2 * pad
        draw.text((x + pad, top + 22), label, font=_fit_font(draw, label, inner_w, 26, bold=False), fill=INK_MUTED)
        draw.text((x + pad, top + 62), value, font=_fit_font(draw, value, inner_w, 46), fill=INK_PRIMARY)

    draw.text(
        (56, CARD_H - 46),
        "Scrypt merged mining · shares its miner base with Litecoin & Dogecoin",
        font=f_foot,
        fill=INK_MUTED,
    )

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
