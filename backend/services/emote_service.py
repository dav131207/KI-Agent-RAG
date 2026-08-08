"""Context-aware local emote selection."""

import random
import re
from pathlib import Path
from typing import Optional

from core.config import BACKEND_DIR

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


def pick_emote(text: str) -> Optional[str]:
    """Pick a context-aware local emote based on the provided text."""
    if not emote_files:
        return None

    text_lower = text.lower()

    emote_scores = []
    for emote in emote_files:
        name = emote.name.lower()
        tokens = re.findall(r"[a-z]+", name)
        score = sum(1 for token in tokens if len(token) > 2 and token in text_lower)
        emote_scores.append((emote.name, score))

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
