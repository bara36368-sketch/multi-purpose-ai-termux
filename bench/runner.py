"""Benchmark runner: measure tok/s, tokens/J, thermals for a model on a device.

Usage (on the phone, androidllm-serve already running):
    python runner.py --model qwen3-8b --device g85 --reps 3 --prompt "Hello world"
    python runner.py --model qwen15 --device g85 --stream        # SSE streaming
    python runner.py --list-devices
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from metrics import summarize, watt_seconds  # noqa: E402
from profiles import PROFILES, get_profile  # noqa: E402


def _count_tokens(resp):
    try:
        return int(resp["usage"]["completion_tokens"])
    except Exception:
        return None


def _stream_tokens(provider, messages, max_tokens):
    n = 0
    for chunk in provider.chat(messages, max_tokens=max_tokens, stream=True):
        try:
            n += len(chunk["choices"][0]["delta"].get("content") or "")
        except Exception:
            pass
    return n


def run_bench(model, device_name, base_url, api_key, prompt, max_tokens,
              reps, stream, rng_seed=7):
    from providers import AndroidLLM

    device = get_profile(device_name)
    provider = AndroidLLM(base_url, api_key, model)
    if not provider.health():
        raise SystemExit(f"androidllm not healthy at {base_url}/health — is serve running?")

    before = device.snapshot()
    messages = [{"role": "user", "content": prompt}]

    t0 = time.monotonic()
    total = 0
    for i in range(reps):
        if stream:
            total += _stream_tokens(provider, messages, max_tokens)
        else:
            resp = provider.chat(messages, max_tokens=max_tokens)
            n = _count_tokens(resp)
            if n is None:
                raise SystemExit(f"no usage.completion_tokens in response: {str(resp)[:200]}")
            total += n
        print(f"  rep {i + 1}/{reps}: {total} tokens cumulative")
    seconds = time.monotonic() - t0
    after = device.snapshot()

    charge_delta = 0.0
    if before["charge_mah"] is not None and after["charge_mah"] is not None:
        charge_delta = before["charge_mah"] - after["charge_mah"]

    return summarize({
        "tokens": total, "seconds": seconds,
        "joules": watt_seconds(charge_delta) if charge_delta > 0 else 0.0,
        "temp_before_c": before["thermal_c"], "temp_after_c": after["thermal_c"],
        "model": model, "device": device.name,
        "ram_tier_gb": None, "timestamp": int(time.time()),
        "stream": stream, "reps": reps, "prompt": prompt, "rng_seed": rng_seed,
    })


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bench-runner", description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--device", default="generic", choices=list(PROFILES) + ["generic"])
    ap.add_argument("--url", default=os.environ.get("ANDROIDLLM_URL", "http://127.0.0.1:8080"))
    ap.add_argument("--key", default=os.environ.get("ANDROIDLLM_KEY"))
    ap.add_argument("--prompt", default="Tell me about the history of Rome in detail.")
    ap.add_argument("--max-tokens", type=int, default=128)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--out", help="write JSON result to this file")
    ap.add_argument("--list-devices", action="store_true")
    args = ap.parse_args(argv)

    if args.list_devices:
        print("\n".join(sorted(PROFILES)))
        return 0

    result = run_bench(args.model, args.device, args.url, args.key,
                       args.prompt, args.max_tokens, args.reps, args.stream)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=1)
        print(f"wrote {args.out}")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
