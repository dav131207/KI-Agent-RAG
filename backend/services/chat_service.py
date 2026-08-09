"""Chat and content generation services."""

import re
from typing import AsyncGenerator, Optional

from analytics import track_event
from core.config import DEFAULT_MODEL, SYSTEM_PROMPT_PATH
from core.providers import get_llm_provider
from core.providers.base import LLMError
from fastapi import HTTPException
from services.crypto_service import get_pepe_market_data
from core.http import http

if SYSTEM_PROMPT_PATH.exists():
    _system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
else:
    _system_prompt = (
        "You are Professor Pepe, a helpful AI assistant. Answer clearly and concisely. "
        "Use markdown formatting when it helps readability. "
        "Always refer to yourself as Professor Pepe. Do not mention that you are an AI model built by Google."
    )


def is_social_command(message: str) -> bool:
    """Detect the built-in 'create (a) social media post' command."""
    return bool(
        re.match(r"^create\s+a?\s*social\s+media\s+post", (message or "").strip(), re.IGNORECASE)
    )


def build_contents(
    topic: str,
    message: str,
    history: list[dict],
    context: str = "",
    language: Optional[str] = None,
):
    """Build the list of messages sent to the LLM."""
    system = _system_prompt
    if context:
        system += (
            "\n\nUse the following knowledge to answer the user's question. "
            "If the knowledge does not contain the answer, say so honestly.\n\n"
            f"{context}"
        )
    if topic:
        system += (
            f"\n\nThe user is asking about the topic: {topic}. "
            "Stay focused on this topic when relevant."
        )

    if language:
        system += (
            f"\n\nIMPORTANT: The user is located in a {language}-speaking region. "
            f"Respond entirely in {language}, including all links and commands."
        )

    if is_social_command(message):
        platform_match = re.search(r"Platform:\s*(\w+)", message, re.IGNORECASE)
        platform = platform_match.group(1).lower() if platform_match else "twitter"

        system += "\n\nYou are generating a social media post. "
        tonality_match = re.search(r"Tonality:\s*([\w\s-]+)\.", message, re.IGNORECASE)
        strategy = (tonality_match.group(1).strip().lower() if tonality_match else "standard").replace(" ", "-")

        if platform == "twitter":
            system += "Keep the final text under 280 characters. "
            if "brokerage" in strategy:
                system += (
                    "You are acting as a 'Broker' bridging the Pepe/Crypto cluster with the Public Sector/Govtech/Tech cluster. "
                    "Use the formula: 'What [specific Pepe/Counterparty historical detail] teaches us about [broad Tech/Public Sector problem]'. "
                    "CRITICAL CONSTRAINTS:\n"
                    "1. Focus strictly on PROVENANCE (verifiable ownership history without a custodian). Do NOT claim Counterparty allows 'trustless micro-settlements' (it failed at settlement due to high fees and 10-minute block times).\n"
                    "2. Remember that Counterparty is a metalayer over Bitcoin (data in OP_RETURN), not a UTXO-native issuance protocol.\n"
                    "3. Do NOT force an 'AI' or 'machine-to-machine' angle. Frame it honestly as a 10-year-old empirical case study for the longevity of public registry data (which survived without API migrations or custodians).\n"
                    "4. Use a highly precise, academic, and analytical tone. Acknowledge what failed (settlement) to build credibility for what worked (provenance).\n"
                    "5. Do NOT use any cashtags (like $PEP) or crypto-slang to prevent cluster-anchoring."
                )
            elif "mid-tier" in strategy or "reply" in strategy:
                system += (
                    "You are replying to a tweet from a mid-tier account (10k-150k followers) in an adjacent tech/policy cluster. "
                    "Add immense structural value or a unique 'Broker' perspective. "
                    "Do not shill or act promotional. CRITICAL: Do NOT use any cashtags (like $PEP) or crypto-slang."
                )
            elif "engagement" in strategy:
                system += (
                    "Generate a post that ends with a structural or architectural question about Tech/Crypto to force replies from 'weak ties'. "
                    "Focus on provoking a thoughtful discussion. CRITICAL: Do NOT use any cashtags (like $PEP)."
                )
            else:
                # Standard (In-Cluster)
                system += (
                    "Always include @PepecoinNetwork, @dogecoin, @litecoin and @Bitcoin. "
                    "Use relevant cashtags like $PEP. "
                    "CRITICAL: Use ONLY 0 to 1 emojis maximum in the entire post. "
                    "CRITICAL: Be extremely creative. Use high variance in sentence structure, vocabulary, and angles."
                )

        elif platform == "reddit":
            system += (
                "Format this as a subtle, organic Reddit text post (use markdown). "
                "Keep it concise, conversational, and non-promotional. "
                "Do not write it like an ad or 'Due Diligence' unless explicitly asked. "
                "Do NOT use Twitter @ handles. Refer to Pepecoin natively. "
                "CRITICAL: Do NOT mention other cryptocurrencies like Dogecoin, Litecoin, or Bitcoin unless absolutely necessary to avoid automated spam filters. "
                "CRITICAL: Avoid words like 'buy', 'invest', 'moon', 'gem', or 'pump'. "
                "NEVER suggest or include images for Reddit posts. "
                "Focus on asking genuine questions or sharing a quick, casual thought to spark comments. "
                "CRITICAL: To prevent the user from copy-pasting the suggestions into the post, you MUST wrap the actual post text in a markdown blockquote (using >). "
                "Then, UNDERNEATH the blockquote, suggest 2-3 highly relevant Subreddits where this post would perform best, formatted as: 'Suggested Subreddits: r/Subreddit1, r/Subreddit2'."
            )
            if "shill" in strategy:
                system += (
                    "\n\nSHILL MODE ACTIVATED: Your goal is to hack the Reddit algorithm subtly. "
                    "You must NOT sound like a marketer. Pose as a curious community member or skeptic. "
                    "Write a slightly contrarian take or a 'stupid' question that forces people to correct you in the comments (Cunningham's Law). "
                    "The goal is organic comment volume, which triggers the algorithm."
                )
        elif platform == "tiktok":
            system += (
                "Format this as a ready-to-post TikTok caption. "
                "Do not write a video script or visual cues. Just write the highly engaging text caption that goes under the video. "
                "Keep it punchy, conversational, and highly engaging for Gen-Z. "
                "Include a strong text hook at the very beginning. "
                "Include viral hashtags like #Pepecoin #Crypto #Web3 and ask a question to drive comments."
            )
            if "shill" in strategy:
                system += (
                    "\n\nSHILL MODE ACTIVATED: Your goal is to hack the TikTok algorithm. "
                    "Optimize the caption to boost engagement (likes, shares, saves, and comments). "
                    "Tease a 'secret' or controversial take in the first line so people rewatch the video. "
                    "Tell viewers to 'save this video' or 'share with a fren' to push it into the algorithm."
                )

    contents = [{"role": "user", "parts": [{"text": system}]}]
    for turn in history[-10:]:
        role = turn.get("role")
        text = turn.get("text", "")
        if role == "user":
            contents.append({"role": "user", "parts": [{"text": text}]})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": message}]})
    return contents


def format_social_post(text: str, platform: str = "twitter", strategy: str = "standard") -> str:
    """Normalize coin names to X/Twitter handles and ensure @PepecoinNetwork only for standard posts."""
    text = (text or "").strip()

    if platform != "twitter":
        return text

    if strategy == "standard":
        text = re.sub(r"(?<!@)\bDogecoin\b", "@dogecoin", text, flags=re.IGNORECASE)
        text = re.sub(r"(?<!@)\bLitecoin\b", "@litecoin", text, flags=re.IGNORECASE)
        text = re.sub(r"(?<!@)\bBitcoin\b", "@Bitcoin", text, flags=re.IGNORECASE)

        handle = "@PepecoinNetwork"
        if not re.search(r"@pepecoinnetwork\b", text, re.IGNORECASE):
            suffix = " " + handle
            if len(text) + len(suffix) > 280:
                text = text[: max(0, 280 - len(suffix))].rstrip()
            text = text + suffix

    return text[:280]


GET_COINS_TEXTS = {
    "English": (
        "Want free PEP, fren? Here's how to get started:\n\n"
        "- **Faucet** – claim free PEP risk-free: "
        "[pepeblocks.com/faucet](https://pepeblocks.com/faucet)\n"
        "- **Wallet** – Coinomi supports native PEP (addresses start with P, never 0x): "
        "[coinomi.com](https://www.coinomi.com/)\n"
        "- **Discord** – community, support and airdrops: "
        "[Join Discord](discord.gg/UnyMVjM9rv)\n"
        "- **Tipping channel** – ongoing airdrops: "
        "[Open channel](https://discord.com/channels/1162499246503759962/1203748781590577222)\n\n"
        "One coin. One community."
    ),
    "German": (
        "Willst du gratis PEP, fren? So geht's:\n\n"
        "- **Faucet** – hole dir risikofrei gratis PEP: "
        "[pepeblocks.com/faucet](https://pepeblocks.com/faucet)\n"
        "- **Wallet** – Coinomi unterstützt natives PEP (Adressen beginnen mit P, nie 0x): "
        "[coinomi.com](https://www.coinomi.com/)\n"
        "- **Discord** – Community, Support und Airdrops: "
        "[Discord beitreten](discord.gg/UnyMVjM9rv)\n"
        "- **Tipping-Kanal** – laufende Airdrops: "
        "[Kanal öffnen](https://discord.com/channels/1162499246503759962/1203748781590577222)\n\n"
        "One coin. One community."
    ),
}


def get_llm():
    """Return a configured LLM provider or raise an HTTPException."""
    provider = get_llm_provider()
    if not provider.is_configured:
        raise HTTPException(status_code=500, detail="LLM provider not configured")
    return provider


async def generate_chat_response(
    topic: str,
    message: str,
    history: list[dict],
    context: str = "",
    language: Optional[str] = None,
    stream: bool = True,
    base_url: str = "",
) -> AsyncGenerator[str, None] | str:
    """Generate a chat response, optionally streaming."""
    provider = get_llm()
    
    crypto_context = await get_pepe_market_data(http)
    if crypto_context:
        context = (context + "\n\n" + crypto_context).strip()
        
    contents = build_contents(topic, message, history, context, language)
    is_social = is_social_command(message)

    if stream:
        async def streamer():
            try:
                if is_social:
                    platform_match = re.search(r"Platform:\s*(\w+)", message, re.IGNORECASE)
                    platform = platform_match.group(1).lower() if platform_match else "twitter"
                    tonality_match = re.search(r"Tonality:\s*([\w\s-]+)\.", message, re.IGNORECASE)
                    strategy = (tonality_match.group(1).strip().lower() if tonality_match else "standard").replace(" ", "-")

                    full = ""
                    async for chunk in provider.stream(DEFAULT_MODEL, contents, temperature=0.9):
                        full += chunk
                    
                    final_text = format_social_post(full, platform, strategy)

                    # Auto-Meme Synergy for Standard Twitter strategy
                    if platform == "twitter" and strategy == "standard":
                        from rag.qdrant_store import get_random_pepe_meme
                        from api.routes import _extract_pepe_image_url
                        from services.image_service import build_watermarked_url
                        from pathlib import Path
                        
                        pepe = get_random_pepe_meme()
                        if pepe:
                            ext_url = _extract_pepe_image_url(pepe)
                            filename = pepe.get("filename", "")
                            if not filename and pepe.get("file_path"):
                                filename = Path(pepe["file_path"]).name
                            meme_url = build_watermarked_url(base_url, ext_url, filename)
                            final_text += f"\n\n![Rare Pepe]({meme_url})"
                    
                    yield final_text
                    return

                async for chunk in provider.stream(DEFAULT_MODEL, contents):
                    yield chunk
            except Exception as e:
                track_event(
                    client_ip=None,
                    event_type="error",
                    command="chat_stream",
                    message=str(e)[:300],
                )
                yield "\n\n⚠️ Sorry fren, something went wrong generating this response. Please try again."

        return streamer()

    try:
        kwargs = {"temperature": 0.9} if is_social else {}
        text = provider.generate(DEFAULT_MODEL, contents, **kwargs)
    except LLMError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    if is_social:
        platform_match = re.search(r"Platform:\s*(\w+)", message, re.IGNORECASE)
        platform = platform_match.group(1).lower() if platform_match else "twitter"
        text = format_social_post(text, platform, getattr(req, "strategy", "standard"))  # In the non-stream case, strategy isn't easily parsed here yet, but standard is safe fallback. Let's parse it.
        tonality_match = re.search(r"Tonality:\s*([\w\s-]+)\.", message, re.IGNORECASE)
        strategy = (tonality_match.group(1).strip().lower() if tonality_match else "standard").replace(" ", "-")
        text = format_social_post(text, platform, strategy)
    return text
