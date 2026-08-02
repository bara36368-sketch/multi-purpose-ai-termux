"""Benchmark metrics: tok/s, tokens/J, temperature deltas.

All numbers derivable from wall-clock + battery/thermal sysfs so runs stay
offline and reproducible.
"""
import time


def timed(fn, reps=1):
    """Run fn() reps times, return (results, total_seconds)."""
    out = []
    start = time.monotonic()
    for _ in range(reps):
        out.append(fn())
    return out, time.monotonic() - start


def tokens_per_second(total_tokens, seconds):
    return round(total_tokens / seconds, 2) if seconds > 0 else 0.0


def tokens_per_joule(total_tokens, joule_delta):
    return round(total_tokens / joule_delta, 2) if joule_delta > 0 else None


def watt_seconds(charge_mah, voltage_v=3.85):
    """Convert battery charge deltas (mAh) to Joules."""
    return round(charge_mah / 1000.0 * voltage_v * 3600.0, 1)


def temp_delta(before_c, after_c):
    if before_c is None or after_c is None:
        return None
    return round(after_c - before_c, 1)


def summarize(result):
    """result: dict with tokens, seconds, joules, temp_before, temp_after.
    Returns the JSON-safe metric set."""
    tps = tokens_per_second(result["tokens"], result["seconds"])
    return {
        "tokens": result["tokens"],
        "seconds": round(result["seconds"], 3),
        "tokens_per_sec": tps,
        "tokens_per_joule": tokens_per_joule(result["tokens"], result.get("joules", 0)),
        "joules": round(result.get("joules", 0), 1),
        "temp_before_c": result.get("temp_before_c"),
        "temp_after_c": result.get("temp_after_c"),
        "temp_delta_c": temp_delta(result.get("temp_before_c"), result.get("temp_after_c")),
        "model": result.get("model"),
        "device": result.get("device"),
        "ram_tier_gb": result.get("ram_tier_gb"),
        "timestamp": result.get("timestamp"),
    }
