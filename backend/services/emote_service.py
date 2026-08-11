"""Context-aware local emote selection."""

import random
import re
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from PIL import Image, ImageSequence

from core.config import BACKEND_DIR

# Emotes are 112x112 or smaller. X renders media several hundred pixels wide,
# so served at native size they arrive blurred by the client's upscaler.
EMOTE_EXPORT_SIZE = 512

EMOTES_DIR = BACKEND_DIR.parent / "frontend" / "dist" / "emotes"
if not EMOTES_DIR.exists():
    EMOTES_DIR = BACKEND_DIR.parent / "frontend" / "public" / "emotes"

emote_files = sorted([f for f in EMOTES_DIR.iterdir() if f.is_file()]) if EMOTES_DIR.exists() else []

EMOTE_KEYWORDS = {
    "happy": ["Happy", "Hype", "Party", "Dance", "Smile", "Joy", "Celebrate", "Excited"],
    "sad": ["Sad", "Cry", "Tears", "Depress", "Sob", "Pain", "Suffer"],
    "angry": ["Angery", "Angry", "Mad", "Rage", "Ree", "Trigger", "Fuck"],
    "confused": ["Confus", "Wot", "Woah", "Huh", "Question", "Weird"],
    "love": ["Love", "Heart", "Kiss", "Blush", "Booba", "Lewd"],
    "sleep": ["Sleep", "Tired", "Nap", "Yawn"],
    "rich": ["Money", "Credit", "Rich", "Gold", "Patreon", "Nitro"],
    "cool": ["Cool", "Sunglasses", "Tuxedo", "Jedi", "Sith", "Lightsaber"],
    "food": ["Food", "Eat", "Drink", "Sip", "Burger", "Pizza"],
    "gaming": ["Minecraft", "Game", "Gaming", "Imposter", "Pirate"],
    "christmas": ["Christmas", "Santa", "Xmas"],
    "pride": ["Pride", "Gay", "Lesbian", "Trans", "Bisexual", "NonBinary"],
    "sign": ["Sign", "NoSign", "Stop", "BoiStop"],
    "default": [],
}


# Words that put a mood in play, beyond the mood's own name.
MOOD_TRIGGERS = {
    "happy": ["happy", "hype", "joy", "great", "nice", "party", "celebrate", "win", "lol", "haha", "funny"],
    "sad": ["sad", "cry", "sorry", "miss", "hurt", "lost", "down", "rip"],
    "angry": ["angry", "angery", "mad", "rage", "hate", "annoy", "wtf", "scam"],
    "confused": ["confused", "huh", "what", "why", "weird", "strange", "unsure"],
    "love": ["love", "heart", "kiss", "cute", "adore", "fren", "thank"],
    "sleep": ["sleep", "tired", "nap", "yawn", "bed", "night"],
    "rich": ["money", "rich", "gold", "profit", "pump", "buy", "price", "market"],
    "cool": ["cool", "based", "chad", "smooth", "clean", "sharp"],
    "food": ["food", "eat", "drink", "hungry", "coffee", "beer", "pizza"],
    "gaming": ["game", "gaming", "play", "minecraft", "noob", "gg"],
    "christmas": ["christmas", "santa", "xmas", "holiday", "winter"],
    "pride": ["pride", "rainbow"],
    "sign": ["sign", "stop", "no", "warning"],
}


def _score_emotes(text: str) -> list[tuple[str, int]]:
    """
    Score every emote against the text.

    EMOTE_KEYWORDS maps a mood to the filename fragments that express it, but
    nothing ever read it: matching compared whole filename tokens against the
    text, so an emote called HappyTalk only scored if the text contained
    "happytalk". It never did, which left the choice effectively random.
    """
    text_lower = (text or "").lower()

    fragments: list[str] = []
    for mood, mood_fragments in EMOTE_KEYWORDS.items():
        triggers = MOOD_TRIGGERS.get(mood, []) + [mood]
        if any(re.search(rf"\b{re.escape(t)}", text_lower) for t in triggers):
            fragments.extend(f.lower() for f in mood_fragments)

    scored = []
    for emote in emote_files:
        name = emote.name.lower()
        # Mood match is the primary signal; a literal filename token in the
        # text is kept as a weaker one, since it does occasionally fire.
        score = 2 * sum(1 for fragment in fragments if fragment in name)
        tokens = re.findall(r"[a-z]+", name)
        score += sum(1 for token in tokens if len(token) > 3 and token in text_lower)
        scored.append((emote.name, score))
    return scored


def suggest_emotes(text: str, limit: int = 4, animated_only: bool = False) -> list[str]:
    """
    Return the best-matching emote filenames, best first.

    Unlike pick_emote this does not collapse to a single random choice: the
    caller picks from the shortlist, so a mismatch is theirs to reject rather
    than something that silently lands under a post.
    """
    if not emote_files:
        return []

    scored = _score_emotes(text)
    if animated_only:
        gifs = {e.name for e in emote_files if e.suffix.lower() == ".gif"}
        scored = [(name, s) for name, s in scored if name in gifs]
        if not scored:
            return []

    matches = sorted(
        [item for item in scored if item[1] > 0], key=lambda x: x[1], reverse=True
    )
    names = [name for name, _ in matches[:limit]]

    # Nothing matched the text — fall back to a random spread so the picker is
    # never empty, since any emote beats none for a post that wants one.
    if len(names) < limit:
        pool = [name for name, _ in scored if name not in names]
        random.shuffle(pool)
        names.extend(pool[: limit - len(names)])
    return names[:limit]


def pick_emote(text: str) -> Optional[str]:
    """Pick a context-aware local emote based on the provided text."""
    if not emote_files:
        return None

    emote_scores = _score_emotes(text)
    max_score = max((s for _, s in emote_scores), default=0)
    if max_score > 0:
        candidates = [name for name, score in emote_scores if score == max_score]
    else:
        neutral = [
            "Pepe Server 1_PES_PoggerSip.png",
            "Pepe Server 2_PES2_HypeTuxedo.png",
            "Pepe Server 2_PES2_BlushShrug.png",
            "Pepe Server 1_PES_Sleep.png",
            "Pepe Server 2_PES2_Woah.png",
            "Pepe Server 2_aPES2_HappyTalk.gif",
            "Pepe Server 1_PES_Angery.png",
            "Pepe Server 2_PES2_SadGeGun.png",
        ]
        candidates = [n for n in neutral if n in [e.name for e in emote_files]]
        if not candidates:
            candidates = [e.name for e in emote_files]

    return f"/emotes/{random.choice(candidates)}"


def resolve_emote_path(filename: str) -> Path:
    """Resolve an emote filename to a path inside EMOTES_DIR, or 404/400."""
    if not EMOTES_DIR.exists():
        raise HTTPException(status_code=503, detail="No emotes available")

    path = (EMOTES_DIR / filename).resolve()
    root = EMOTES_DIR.resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Emote not found")
    return path


def export_emote(filename: str, size: int = EMOTE_EXPORT_SIZE) -> tuple[bytes, str]:
    """
    Return an emote scaled up for social media, as (bytes, media type).

    Animated GIFs are resized frame by frame and written back with save_all;
    the watermark path flattens them to a single PNG frame, which is why this
    does not go through it. Nearest-neighbour keeps these hard-edged sprites
    crisp — a smooth filter turns them to mush at 4x.
    """
    path = resolve_emote_path(filename)
    image = Image.open(path)

    width, height = image.size
    scale = max(1, size // max(width, height))
    target = (width * scale, height * scale)

    buf = BytesIO()
    if getattr(image, "n_frames", 1) > 1:
        frames = [
            frame.copy().resize(target, Image.NEAREST)
            for frame in ImageSequence.Iterator(image)
        ]
        frames[0].save(
            buf,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            loop=image.info.get("loop", 0),
            duration=image.info.get("duration", 100),
            disposal=image.info.get("disposal", 2),
            transparency=image.info.get("transparency", 255),
        )
        return buf.getvalue(), "image/gif"

    image.convert("RGBA").resize(target, Image.NEAREST).save(buf, format="PNG")
    return buf.getvalue(), "image/png"
