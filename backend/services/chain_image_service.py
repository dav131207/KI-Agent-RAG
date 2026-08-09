"""
Render a live on-chain stat card for Pepecoin.

The metrics (hashrate, difficulty, block height, peers) are in different units,
so they are shown as separate hero numbers rather than plotted together on a
shared axis. Rendering happens locally with Pillow so the numbers are not handed
to a third-party chart service.
"""

from datetime import datetime, timezone
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


def _fmt_timestamp(fetched_at: Optional[float]) -> str:
    """Render the fetch time in UTC so the card states how current it is."""
    if not fetched_at:
        return "live"
    return datetime.fromtimestamp(fetched_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


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


def _metric_tiles(chain: dict[str, Any]) -> dict[str, tuple[str, str, str]]:
    """
    Every metric the card can show, as {key: (hero label, tile label, value)}.

    The tile label is the short form: a headline has the full card width, a
    132px tile does not.
    """
    block_time = chain.get("avg_block_time_s")
    return {
        "hashrate": ("NETWORK HASHRATE", "HASHRATE", format_hashrate(chain.get("hashrate_ths"))),
        "blocktime": ("AVG BLOCK TIME", "BLOCK TIME", f"{block_time:.0f}s" if block_time else "n/a"),
        "difficulty": ("DIFFICULTY", "DIFFICULTY", _fmt_int(chain.get("difficulty"))),
        "height": ("BLOCK HEIGHT", "HEIGHT", _fmt_int(chain.get("block_height"))),
        "supply": ("SUPPLY", "SUPPLY", _fmt_supply(chain.get("supply"))),
        "peers": ("PEERS", "PEERS", _fmt_int(chain.get("connection_count"))),
    }


def _pick_hero(chain: dict[str, Any], metric: Optional[str]) -> str:
    """
    Choose which metric leads the card.

    Falls through to the next available metric when the requested one has no
    value, so a blocked explorer never puts an "n/a" in the headline.
    """
    tiles = _metric_tiles(chain)
    order = [metric] if metric else []
    order += ["hashrate", "blocktime", "difficulty", "height"]

    for key in order:
        if key in tiles and tiles[key][2] != "n/a":
            return key
    return "height"


def render_chain_stats_card(
    chain: dict[str, Any], metric: Optional[str] = None
) -> Optional[bytes]:
    """
    Render the on-chain snapshot as a PNG stat card. Returns None if empty.

    `metric` selects the headline figure so consecutive posts do not all lead
    with the same number.
    """
    if not chain:
        return None

    img = Image.new("RGB", (CARD_W, CARD_H), SURFACE)
    draw = ImageDraw.Draw(img)

    f_label = _font(26)
    f_title = _font(34, bold=True)
    f_foot = _font(22)

    draw.text((56, 44), "PEPECOIN NETWORK", font=f_title, fill=INK_PRIMARY)
    subtitle = f"{_source_label(chain)} · {_fmt_timestamp(chain.get('fetched_at'))}"
    draw.text((56, 92), subtitle, font=f_label, fill=INK_MUTED)

    # Headline metric: network hashrate.
    tiles = _metric_tiles(chain)
    hero_key = _pick_hero(chain, metric)
    hero_label, _short, hero = tiles[hero_key]

    draw.text((56, 168), hero_label, font=f_label, fill=INK_MUTED)
    draw.text((56, 204), hero, font=_fit_font(draw, hero, CARD_W - 112, 96), fill=ACCENT)

    # Supporting metrics, each in its own unit — deliberately not co-plotted.
    # Fill the row with the best available metrics, skipping the headline so it
    # is never printed twice, and dropping any that have no value.
    stats = [
        (tiles[key][1], tiles[key][2])
        for key in ("height", "hashrate", "difficulty", "blocktime", "supply", "peers")
        if key != hero_key and tiles[key][2] != "n/a"
    ][:4]

    margin, gap, box_h, top = 56, 16, 132, 350
    pad = 20
    # Derive the box width from the margins so the row stays symmetric. With a
    # single reachable source the row can come out empty, hence the guard.
    box_w = (
        (CARD_W - 2 * margin - gap * (len(stats) - 1)) // len(stats) if stats else 0
    )

    inner_w = box_w - 2 * pad
    # One label size for the whole row: sizing each label on its own makes the
    # longest one visibly smaller than its neighbours.
    label_size = 26
    while label_size > 14 and any(
        draw.textlength(label, font=_font(label_size)) > inner_w for label, _ in stats
    ):
        label_size -= 2
    f_tile_label = _font(label_size)

    for i, (label, value) in enumerate(stats):
        x = margin + i * (box_w + gap)
        draw.rounded_rectangle([x, top, x + box_w, top + box_h], radius=10, fill=PANEL)
        draw.text((x + pad, top + 22), label, font=f_tile_label, fill=INK_MUTED)
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
