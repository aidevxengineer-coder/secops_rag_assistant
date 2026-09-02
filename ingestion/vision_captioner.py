"""
Image captioning via Groq vision, rotating across multiple API keys.

Rotation logic: each key is used for up to REQUESTS_PER_KEY_LIMIT requests,
then we move to the next key. When all keys are exhausted, we wait until
the next UTC day (Groq's RPD counters reset at midnight UTC) before resuming.

NOTE: qwen/qwen3.6-27b is capped at 500 RPD per Groq's own model listing
(not the default 1000 RPD most other models get). It is a preview model,
meaning Groq could change or discontinue it without much notice -- check
https://console.groq.com/docs/models before running this at scale, and
https://console.groq.com/docs/deprecations to confirm it hasn't moved to
deprecated status since this was written.
"""

import os
import json
import base64
from pathlib import Path
from datetime import datetime, timezone

from groq import Groq
from .config import Config

# ---- config ----
GROQ_API_KEYS = [
    Config.GROQ_API_KEY_1,  # account 1
    Config.GROQ_API_KEY_2,  # account 2
    Config.GROQ_API_KEY_3,  # account 3
]
# 3 accounts x 500 RPD each = 1500/day total, should clear ~1600-1900 images
# in 1-2 days depending on your exact image count.
MODEL = "qwen/qwen3.6-27b"  # Groq's current vision model, confirmed not deprecated as of this run
REQUESTS_PER_KEY_LIMIT = 498  # stay just under the 500 RPD cap per key (confirmed via Groq's own model listing)
CHECKPOINT_FILE = "caption_checkpoint.json"
KEY_STATE_FILE = "key_rotation_state.json"

CAPTION_PROMPT = (
    "Describe this image in detail for a document search system. "
    "Focus on: any text/numbers visible, chart/table data if present, "
    "diagram structure, and overall meaning. Be factual and specific. "
    "Respond directly with the description only — no preamble, no step-by-step reasoning."
)

FALLBACK_CAPTION = "Visual Content or Image Data [Image caption unavailable — all API keys exhausted for today.]"


# ---- key rotation state ----
def _load_key_state() -> dict:
    """Tracks per-key request counts and the UTC date they apply to."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if os.path.exists(KEY_STATE_FILE):
        with open(KEY_STATE_FILE, "r") as f:
            state = json.load(f)
        if state.get("date") == today:
            return state
    # new day (or first run) -> reset all counters
    return {"date": today, "counts": [0] * len(GROQ_API_KEYS), "active_index": 0}


def _save_key_state(state: dict):
    with open(KEY_STATE_FILE, "w") as f:
        json.dump(state, f)


class KeyRotator:
    def __init__(self):
        self.state = _load_key_state()
        self.clients = [Groq(api_key=k) for k in GROQ_API_KEYS]

    def _current_index(self) -> int:
        return self.state["active_index"]

    def get_client(self) -> Groq | None:
        """Returns the active client, or None if all keys are exhausted for today."""
        # re-check date in case we've rolled past midnight UTC mid-run
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.state["date"] != today:
            self.state = {
                "date": today,
                "counts": [0] * len(GROQ_API_KEYS),
                "active_index": 0,
            }
            _save_key_state(self.state)

        idx = self._current_index()
        while idx < len(self.clients):
            if self.state["counts"][idx] < REQUESTS_PER_KEY_LIMIT:
                return self.clients[idx]
            idx += 1

        return None  # all keys exhausted today

    def record_request(self):
        idx = self._current_index()
        self.state["counts"][idx] += 1
        if self.state["counts"][idx] >= REQUESTS_PER_KEY_LIMIT:
            self.state["active_index"] += 1
            print(
                f"[key rotation] key {idx + 1} hit {REQUESTS_PER_KEY_LIMIT}/500 daily cap, "
                f"moving to key {idx + 2 if idx + 1 < len(self.clients) else '(none left)'}"
            )
        _save_key_state(self.state)


_rotator = KeyRotator()


# ---- captioning ----
def caption_image(image_path: str, max_retries: int = 3) -> str | None:
    """Returns caption string, or None if all keys are exhausted for today."""
    ext = os.path.splitext(image_path)[1].lstrip(".").lower()
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    for attempt in range(max_retries):
        client = _rotator.get_client()
        if client is None:
            print(
                "[stop] all API keys exhausted for today (RPD limits hit). "
                "Resume tomorrow after UTC midnight reset, or run again later."
            )
            return None

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": CAPTION_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                            },
                        ],
                    }
                ],
                max_tokens=350,
                include_reasoning=False,
            )
            _rotator.record_request()
            return response.choices[0].message.content.strip()

        except Exception as e:
            err_str = str(e)
            if (
                "429" in err_str
                or "RESOURCE_EXHAUSTED" in err_str
                or "rate_limit" in err_str.lower()
            ):
                # this key is done for today even if our local counter disagrees
                print(
                    f"[warn] key {_rotator._current_index() + 1} rate-limited unexpectedly, "
                    f"forcing rotation. {e}"
                )
                _rotator.state["counts"][
                    _rotator._current_index()
                ] = REQUESTS_PER_KEY_LIMIT
                _rotator.state["active_index"] += 1
                _save_key_state(_rotator.state)
                continue
            print(f"[warn] captioning failed for {image_path}: {e}")
            return f"[Image at {os.path.basename(image_path)} — caption unavailable]"

    return (
        f"[Image at {os.path.basename(image_path)} — caption unavailable after retries]"
    )


# ---- checkpointing across the full batch ----
def _load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_checkpoint(captions: dict):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(captions, f, indent=2)


def caption_all_images(image_dir: str) -> dict:
    captions = _load_checkpoint()
    image_paths = sorted(Path(image_dir).rglob("*.png")) + sorted(
        Path(image_dir).rglob("*.jpg")
    )
    remaining = [p for p in image_paths if str(p) not in captions]

    print(
        f"Total images: {len(image_paths)} | Already captioned: {len(captions)} | Remaining: {len(remaining)}"
    )

    for i, path in enumerate(remaining):
        result = caption_image(str(path))
        if result is None:
            captions[str(path)] = FALLBACK_CAPTION
            print(f"Stopped at {i}/{len(remaining)} -- all keys exhausted for today.")
            break

        captions[str(path)] = result
        print(f"[{i + 1}/{len(remaining)}] {path.name}")

        if (i + 1) % 40 == 0:
            _save_checkpoint(captions)

    _save_checkpoint(captions)
    return captions
