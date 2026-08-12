"""
Put a second model side by side with the current one on real post tasks.

Judging a model from its card is guesswork. This sends the exact prompt the app
would send — same persona, same goal instructions, same character limit — to
both, so the comparison is on output rather than on description.

The second model is reached over an OpenAI-compatible endpoint, which is what
vLLM serves. On RunPod that is the vLLM template's URL; anything else speaking
that protocol works too.

Usage:
    cd backend
    venv/bin/python scripts/compare_post_models.py \\
        --endpoint https://<pod>/v1 --model SicariusSicariiStuff/Assistant_Pepe_70B

    # only the current model, no endpoint needed
    venv/bin/python scripts/compare_post_models.py
"""

import argparse
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from core.config import POST_MODEL  # noqa: E402
from core.providers import get_llm_provider  # noqa: E402
from services.chat_service import TWEET_LIMIT, build_contents, parse_social_params  # noqa: E402

# One task per goal that produces a visibly different voice, so the comparison
# covers the range rather than a single flattering example.
TASKS = [
    "Goal: Provoke. Format: Single. Topic: merged mining security",
    "Goal: Community. Format: Single. Topic: the fair launch",
    "Goal: Explain. Format: Thread. Topic: why Pepecoin has no contract address",
    "Goal: Outside. Format: Single. Topic: proof-of-work as shared infrastructure",
]


def _prompt_for(task: str) -> tuple[str, str, list]:
    message = f"create a social media post. Platform: Twitter. Language: English. {task}"
    _platform, goal, _fmt = parse_social_params(message)
    return message, goal, build_contents("", message, [], "", None)


def _flatten(contents: list) -> tuple[str, str]:
    """Split the built prompt into a system part and the user's request."""
    texts = [c["parts"][0]["text"] for c in contents]
    return texts[0], texts[-1]


def _report(label: str, text: str, elapsed: float) -> None:
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    longest = max((len(p) for p in parts), default=0)
    flag = "" if longest <= TWEET_LIMIT else f"  ⚠️ {longest} chars — over the limit"
    print(f"  [{label}]  {elapsed * 1000:.0f}ms  {len(parts)} part(s), longest {longest}{flag}")
    for part in parts:
        print(f"      {part}")
    print()


def run(endpoint: str | None, model: str | None) -> int:
    provider = get_llm_provider()
    if not provider.is_configured:
        print("❌ The current provider is not configured; set GEMINI_API_KEY.")
        return 1

    remote = None
    if endpoint:
        try:
            from openai import OpenAI
        except ImportError:
            print("❌ pip install openai — needed to talk to the OpenAI-compatible endpoint.")
            return 1
        # vLLM ignores the key but the client insists on one.
        remote = OpenAI(base_url=endpoint.rstrip("/"), api_key="local")

    for task in TASKS:
        message, goal, contents = _prompt_for(task)
        system, request = _flatten(contents)
        print(f"=== {goal.upper()} — {task.split('Topic: ')[-1]} ===")

        start = time.perf_counter()
        current = provider.generate(POST_MODEL, contents, temperature=0.9)
        _report(POST_MODEL, (current or "").strip(), time.perf_counter() - start)

        if remote:
            start = time.perf_counter()
            try:
                answer = remote.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": request},
                    ],
                    temperature=0.9,
                    max_tokens=600,
                )
                text = (answer.choices[0].message.content or "").strip()
            except Exception as exc:
                text = f"(failed: {exc})"
            _report(model, text, time.perf_counter() - start)

    if not remote:
        print("Only the current model ran. Pass --endpoint and --model to compare.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare post models on real tasks")
    parser.add_argument("--endpoint", help="OpenAI-compatible base URL, e.g. https://<pod>/v1")
    parser.add_argument("--model", help="Model name to request from that endpoint")
    args = parser.parse_args()
    if bool(args.endpoint) != bool(args.model):
        parser.error("--endpoint and --model go together")
    sys.exit(run(args.endpoint, args.model))
