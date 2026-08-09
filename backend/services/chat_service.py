"""Chat and content generation services."""

import logging
import re
from typing import AsyncGenerator, Optional

from analytics import track_event
from core.config import DEFAULT_MODEL, SYSTEM_PROMPT_PATH
from core.providers import get_llm_provider
from core.providers.base import LLMError
from fastapi import HTTPException
from services.crypto_service import get_pepe_market_data
from core.http import http
import logging

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

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


def parse_social_params(message: str) -> tuple[str, str]:
    """
    Extract (platform, strategy) from a social-post command.

    Both the prompt builder and the post formatter must agree on the strategy,
    so the parsing lives in one place instead of being re-derived per call site.
    """
    message = message or ""

    platform_match = re.search(r"Platform:\s*(\w+)", message, re.IGNORECASE)
    platform = platform_match.group(1).lower() if platform_match else "twitter"

    # Prefer the "Tonality: <x>. Topic" form; fall back to a trailing sentence.
    tonality_match = re.search(r"Tonality:\s*(.+?)\.\s*Topic", message, re.IGNORECASE)
    if not tonality_match:
        tonality_match = re.search(r"Tonality:\s*([\w\s-]+)\.", message, re.IGNORECASE)
    strategy = (tonality_match.group(1).strip().lower() if tonality_match else "standard").replace(" ", "-")

    return platform, strategy


TWEET_LIMIT = 280

# Tone instructions for the non-Twitter platforms. The modal offers six
# tonalities but only "shill" used to reach the prompt, so the other five
# produced a byte-identical request and the tone never changed.
TONE_INSTRUCTIONS = {
    "humorous": (
        "TONE — HUMOROUS: Write with dry, self-aware meme humour. Land the joke through "
        "understatement and specific absurd detail, not exclamation marks. One good joke beats "
        "three weak ones. Never explain the joke, and never use 'lol' or laughing emojis."
    ),
    "professional": (
        "TONE — PROFESSIONAL: Direct, factual, sober. No hype words ('massive', 'insane', 'huge'), "
        "no emojis, no exclamation marks. Make claims you can support and attribute numbers to "
        "their source. Short declarative sentences."
    ),
    "hype": (
        "TONE — HYPE: High energy and bullish about the technology and the community. Keep it "
        "about momentum, building and participation — never about price targets, returns, or "
        "predictions, and never imply anyone will make money."
    ),
    "educational": (
        "TONE — EDUCATIONAL: Explain the mechanism so a curious outsider follows it. Define each "
        "technical term the first time it appears. Lead with the concept, use Pepecoin only as the "
        "worked example. No marketing language and no call to action."
    ),
    "philosophical": (
        "TONE — PHILOSOPHICAL: Reflective and abstract, about decentralisation, trust and "
        "permanence. Pose the question rather than answering it. No cashtags, no price talk, no "
        "promotion — the reader should leave thinking, not buying."
    ),
}


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
        platform, strategy = parse_social_params(message)

        system += "\n\nYou are generating a social media post. "

        if platform == "twitter":
            system += "Format the post for Twitter. If it requires more space than a single tweet which consists of 280 signs, format it as a THREAD (e.g., 1/ ..., 2/ ...). Keep each part very concise. "
            system += "Do NOT include any external links (URLs) in the post text, as the X algorithm suppresses reach for external links. If a link is needed, write '(Link in the replies)' instead. "
            if "brokerage" in strategy:
                system += (
                    "You are acting as a 'Broker' bridging the Pepe/Crypto cluster with the Public Sector/Govtech/Tech cluster. "
                    "CRITICAL CONSTRAINTS FOR THE TWEET:\n"
                    "1. NO BUZZWORDS: Ban words like 'cryptographic', 'trustless', 'decentralized', 'institutional auditability'. Use NO adjectives you cannot empirically prove.\n"
                    "2. BE SPECIFIC: You MUST explicitly say 'Rare Pepe on Counterparty (2016)'. Do NOT abstract it away. The contrast between meme collectors and serious data persistence is the hook.\n"
                    "3. THE CORE THESIS: Focus entirely on 'Persistence without institutional carrier'. Public registries fail due to format migrations, agency closures, and budgets. Rare Pepe survived 10 years without a database admin or budget.\n"
                    "4. CREDIBILITY & NUANCE: Do not say it 'proved' anything; say it 'shows' or 'is evidence of'. Acknowledge the 'catch': persistence rides on Bitcoin's economic incentive structure instead of a department budget. Also explicitly admit it failed at settlement (slow, expensive).\n"
                    "5. Do NOT use any cashtags (like $PEP) or crypto-slang. End by inviting pushback from policy/tech experts."
                )
            elif "miner" in strategy or "synergy" in strategy:
                system += (
                    "You are generating a highly analytical post targeting the Dogecoin/Litecoin mining community and Cypherpunks. "
                    "CRITICAL CONSTRAINTS:\n"
                    "1. Focus strictly on the CATEGORY: Scrypt merged mining, UTXO economics, PoW, Hashrate, or Node distribution.\n"
                    "2. Pepecoin is just the EXAMPlE, not the subject. Do not sound like an ad. No price talk, no 'next 100x'.\n"
                    "3. USE DATA: Reference hashrate development, node numbers, or block times. Mention that Pepecoin shares the exact same physical miner base as Doge/Litecoin.\n"
                    "4. ADMIT WEAKNESSES: Build credibility by admitting the limits of merged mining (e.g. 'borrowed hashrate').\n"
                    "5. Use relevant hashtags/cashtags ($DOGE, $LTC, $PEP) but keep it academic and structural."
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

        # Twitter picks a strategy rather than a tonality, so the tone block
        # only applies to the platforms whose modal offers tonalities.
        if platform != "twitter":
            for tone_key, instruction in TONE_INSTRUCTIONS.items():
                if tone_key in strategy:
                    system += f"\n\n{instruction}"
                    break

        if platform == "twitter":
            system += (
                f"\n\nHARD LIMIT: every single tweet must be at most {TWEET_LIMIT} characters, "
                "counted including spaces, hashtags and handles. If the content does not fit, "
                "split it into a numbered thread where each part is under the limit on its own. "
                "Do not pad to reach the limit — shorter is fine."
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


def _split_sentences(text: str) -> list[str]:
    """Break text into sentences, keeping their terminating punctuation."""
    parts = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    return [p.strip() for p in parts if p.strip()]


def _hard_wrap(chunk: str, limit: int) -> list[str]:
    """Break an over-long sentence at word boundaries as a last resort."""
    out: list[str] = []
    current = ""
    for word in chunk.split():
        # A single token can exceed the limit on its own (a long URL or hashtag
        # chain), and no word boundary will save it — cut it by characters.
        if len(word) > limit:
            if current:
                out.append(current)
                current = ""
            out.extend(word[i : i + limit] for i in range(0, len(word), limit))
            continue
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                out.append(current)
            current = word
    if current:
        out.append(current)
    return out


def enforce_tweet_limit(text: str, limit: int = TWEET_LIMIT) -> str:
    """
    Guarantee every tweet fits the character limit.

    The prompt asks the model to stay under it, but a prompt is a request, not a
    constraint, and appending @PepecoinNetwork can push a compliant post over on
    its own. Over-long text is split into a numbered thread at sentence
    boundaries rather than truncated, so nothing is silently lost.
    """
    text = (text or "").strip()
    if not text:
        return text

    # An existing thread is already split; leave it alone if every part fits.
    existing = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(existing) > 1 and all(len(p) <= limit for p in existing):
        return text
    if len(existing) == 1 and len(text) <= limit:
        return text

    # Reserve room for the "12/34 " prefix added below.
    budget = limit - 7
    chunks: list[str] = []
    current = ""
    for sentence in _split_sentences(text):
        if len(sentence) > budget:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_wrap(sentence, budget))
            continue
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= budget:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)

    if len(chunks) == 1 and len(chunks[0]) <= limit:
        return chunks[0]
    if not chunks:
        return text

    total = len(chunks)
    return "\n\n".join(f"{i}/{total} {chunk}" for i, chunk in enumerate(chunks, 1))


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
            text = text + suffix

    # Applied after the handle and coin substitutions, since both add characters
    # and can push an otherwise compliant post over the limit.
    return enforce_tweet_limit(text)


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
                    platform, strategy = parse_social_params(message)

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
                            
                    # Miner/synergy posts get the live on-chain card, but the
                    # client attaches it alongside the post rather than inlining
                    # it here: the Twitter prompt forbids URLs in the post text,
                    # and markdown pasted into X renders as literal noise.

                    yield final_text
                    return

                async for chunk in provider.stream(DEFAULT_MODEL, contents):
                    yield chunk
            except Exception as e:
                logger.error(f"Streaming error: {e}", exc_info=True)
                yield f"\n\n⚠️ Sorry fren, something went wrong generating this response. Error: {str(e)}"

        return streamer()

    try:
        kwargs = {"temperature": 0.9} if is_social else {}
        text = provider.generate(DEFAULT_MODEL, contents, **kwargs)
    except LLMError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    if is_social:
        platform, strategy = parse_social_params(message)
        text = format_social_post(text, platform, strategy)
    return text
