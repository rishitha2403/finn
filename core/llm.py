import base64
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path

import requests

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

TIERS = {
    "fast": [
        os.getenv("FINN_MODEL_FAST", "gemini-3.5-flash-lite"),
        "gemini-flash-lite-latest",
        "gemini-2.5-flash-lite",
    ],
    "smart": [
        os.getenv("FINN_MODEL_SMART", "gemini-3.8-flash"),
        "gemini-flash-latest",
        "gemini-2.5-flash",
    ],
}

PAID_RATES = {
    "fast": (0.30, 2.50),
    "smart": (0.75, 3.75),
}


def _cache_dir():
    d = os.getenv("FINN_CACHE_DIR")
    if d:
        return Path(d)
    if os.getenv("VERCEL"):
        return Path("/tmp/finn-cache")
    return Path(__file__).resolve().parent.parent / ".cache" / "llm"


class Ledger:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.calls = 0
        self.cached = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.by_tier = {}

    def add(self, tier, model, tin, tout):
        with self.lock:
            self.calls += 1
            self.tokens_in += tin
            self.tokens_out += tout
            t = self.by_tier.setdefault(tier, {"calls": 0, "in": 0, "out": 0, "model": model})
            t["calls"] += 1
            t["in"] += tin
            t["out"] += tout
            t["model"] = model

    def hit(self):
        with self.lock:
            self.cached += 1

    def summary(self):
        usd = 0.0
        for tier, t in self.by_tier.items():
            rin, rout = PAID_RATES.get(tier, (0, 0))
            usd += t["in"] / 1e6 * rin + t["out"] / 1e6 * rout
        return {
            "calls": self.calls,
            "cache_hits": self.cached,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "by_tier": self.by_tier,
            "usd_if_paid": round(usd, 4),
        }


ledger = Ledger()


class LLMError(RuntimeError):
    pass


def available():
    return bool(os.getenv("GEMINI_API_KEY"))


def _key(tier, prompt, pdf):
    h = hashlib.sha256()
    h.update(tier.encode())
    h.update(prompt.encode())
    if pdf:
        h.update(hashlib.sha256(pdf).digest())
    return h.hexdigest()[:32]


def parse_json(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        a = t.find(open_c)
        b = t.rfind(close_c)
        if a != -1 and b > a:
            try:
                return json.loads(t[a:b + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError("model did not return valid JSON")


def ask_json(tier, prompt, pdf=None, max_out=4096, temperature=0.1):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise LLMError("GEMINI_API_KEY is not set")
    ck = _key(tier, prompt, pdf)
    cdir = _cache_dir()
    cpath = cdir / f"{ck}.json"
    if cpath.exists():
        try:
            out = json.loads(cpath.read_text())
            ledger.hit()
            return out
        except Exception:
            pass

    parts = []
    if pdf:
        parts.append({"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(pdf).decode()}})
    parts.append({"text": prompt})
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_out,
            "responseMimeType": "application/json",
        },
    }

    last = None
    for model in TIERS[tier]:
        for attempt in range(3):
            try:
                r = requests.post(
                    ENDPOINT.format(model=model),
                    params={"key": key},
                    json=body,
                    timeout=55,
                )
            except requests.RequestException as e:
                last = e
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code == 404 or (r.status_code == 400 and "model" in r.text.lower()):
                last = LLMError(f"{model}: {r.status_code}")
                break
            if r.status_code in (429, 500, 503):
                last = LLMError(f"{model}: {r.status_code}")
                time.sleep(4 * (attempt + 1))
                continue
            if r.status_code != 200:
                raise LLMError(f"{model}: {r.status_code} {r.text[:300]}")
            data = r.json()
            usage = data.get("usageMetadata", {})
            ledger.add(tier, model, usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0))
            try:
                text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
            except (KeyError, IndexError):
                raise LLMError(f"{model}: empty response")
            out = parse_json(text)
            try:
                cdir.mkdir(parents=True, exist_ok=True)
                cpath.write_text(json.dumps(out))
            except OSError:
                pass
            return out
    raise LLMError(str(last))
