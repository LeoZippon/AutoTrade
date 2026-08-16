#!/usr/bin/env python3
"""Needle-in-a-haystack + BF16-vs-FP8 quality spot-check for Qwen3.8-27B.

Uses the local tokenizer for exact token counts.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import time

import httpx
from transformers import AutoTokenizer

MODEL_DIR = "/Data/public/Qwen3.8-27B"

FILLER_SENTENCES = [
    "The warehouse inventory system tracks part numbers across seven regional depots.",
    "Researchers measured soil moisture content at two hundred sampling sites last autumn.",
    "The committee postponed the budget review until the quarterly figures were audited.",
    "Automated sorting conveyors reduced package handling time by eighteen percent.",
    "The botanical garden added a new greenhouse dedicated to alpine plant species.",
    "Municipal engineers repaved the riverside bike lane and installed new drainage.",
    "The orchestra rehearsed the symphony's third movement twice before the rehearsal ended.",
    "Cartographers updated the hiking trail map after the spring landslide altered the route.",
    "The bakery switched to a slower fermentation schedule to improve the sourdough crust.",
    "Analysts compared trading volumes across futures markets during the volatility spike.",
]


def make_haystack(tok, target_tokens: int, needle: str, depth_frac: float):
    needle_ids = tok.encode(needle)
    budget = target_tokens - len(needle_ids) - 64
    text_parts = []
    total = 0
    j = 0
    while total < budget:
        s = FILLER_SENTENCES[j % len(FILLER_SENTENCES)]
        if j % 13 == 0:
            s = s + f" (ref {j})"
        t = len(tok.encode(s))
        if total + t > budget:
            break
        text_parts.append(s)
        total += t
        j += 1
    cut = int(len(text_parts) * depth_frac)
    return " ".join(text_parts[:cut]) + "\n\n" + needle + "\n\n" + " ".join(text_parts[cut:])


async def needle_test(base_url, api_key, model, tok, ctx_tokens, depth_frac, timeout=900):
    magic = f"MAGIC-{random.randint(100000, 999999)}"
    needle = (
        f"Special note: the maintenance access code for the archive server is {magic}. "
        "Keep this confidential."
    )
    hay = make_haystack(tok, ctx_tokens, needle, depth_frac)
    prompt = (
        hay
        + "\n\nBased on the document above, what is the maintenance access code "
        "for the archive server? Reply with the code only."
    )
    n_tok = len(tok.encode(prompt))
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1200,
        "temperature": 0.0,
        "stream": True,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    t0 = time.perf_counter()
    ttft = None
    answer = []
    usage = {}
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", f"{base_url}/v1/chat/completions",
                                 json=payload, headers=headers) as resp:
            if resp.status_code != 200:
                body = (await resp.aread()).decode()[:200]
                return {"error": f"HTTP {resp.status_code}: {body}", "prompt_tokens": n_tok}
            async for line in resp.aiter_lines():
                if not line.startswith("data: ") or line[6:] == "[DONE]":
                    continue
                try:
                    obj = __import__("json").loads(line[6:])
                except Exception:
                    continue
                if obj.get("usage"):
                    usage = obj["usage"]
                for ch in obj.get("choices") or []:
                    d = ch.get("delta", {})
                    if d.get("content"):
                        if ttft is None:
                            ttft = time.perf_counter() - t0
                        answer.append(d["content"])
    total = time.perf_counter() - t0
    text = "".join(answer).strip()
    hit = magic in text
    pt = usage.get("prompt_tokens", n_tok)
    prefill_tps = pt / ttft if ttft else 0
    return {
        "prompt_tokens": pt, "hit": hit, "ttft": ttft, "total": total,
        "prefill_tps": prefill_tps, "answer": text[:80],
    }


QUALITY_PROMPTS = [
    ("math", "A train travels 240 km in 3 hours, then 130 km in 2 hours. What is its average speed in km/h? Answer with just the number.", 512),
    ("logic", "If all Bloops are Razzies and all Razzies are Lazzies, are all Bloops definitely Lazzies? Answer yes or no with one sentence why.", 512),
    ("code", "Write a Python function is_palindrome(s) that ignores case and non-alphanumeric characters. Keep it under 10 lines.", 2048),
    ("factual", "In one sentence: what is the time complexity of quicksort in the worst case and when does it occur?", 512),
    ("chinese", "用一句话解释什么是 KV cache 量化。", 512),
]


async def quality_test(base_url, api_key, model, label):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    out = {}
    async with httpx.AsyncClient(timeout=300) as client:
        for name, q, mt in QUALITY_PROMPTS:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": q}],
                "max_tokens": mt,
                "temperature": 0.0,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            r = await client.post(f"{base_url}/v1/chat/completions", json=payload, headers=headers)
            if r.status_code != 200:
                out[name] = f"HTTP {r.status_code}"
                continue
            msg = r.json()["choices"][0]["message"]
            out[name] = (msg.get("content") or "").strip()
    return {"label": label, "answers": out}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["needle", "quality"], required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default=os.environ.get("VLLM_API_KEY", ""), help="defaults to $VLLM_API_KEY")
    ap.add_argument("--contexts", default="32000,128000,240000")
    ap.add_argument("--depths", default="0.1,0.5,0.9")
    args = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)

    if args.mode == "quality":
        res = await quality_test(args.base_url, args.api_key, args.model, args.model)
        import json
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    for ctx in [int(x) for x in args.contexts.split(",")]:
        for depth in [float(x) for x in args.depths.split(",")]:
            r = await needle_test(args.base_url, args.api_key, args.model, tok, ctx, depth)
            if "error" in r:
                print(f"ctx={ctx:>6} depth={depth:.0%} ERROR {r['error']}")
            else:
                print(
                    f"ctx={r['prompt_tokens']:>6} depth={depth:.0%} "
                    f"hit={str(r['hit']):>5} ttft={r['ttft']:6.1f}s "
                    f"prefill={r['prefill_tps']:7.0f} t/s total={r['total']:6.1f}s "
                    f"| {r['answer'][:50]}"
                )


if __name__ == "__main__":
    asyncio.run(main())
