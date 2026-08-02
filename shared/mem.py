"""RAM tier detection: /proc/meminfo on Android/Termux, with fallbacks.

Tiers mirror the androidllm model catalog: 5/6/7/8/9/10/12/16 GB.
"""
import os

_TIERS = (5, 6, 7, 8, 9, 10, 12, 16)


def ram_gb():
    try:
        with open("/proc/meminfo", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return round(kb / 1024 / 1024, 1)
    except OSError:
        pass
    try:
        import shutil
        total = shutil.disk_usage("/").total
        return round(total / 1e9, 1)
    except OSError:
        return None


def tier(ram=None):
    """Nearest tier at or below the RAM amount (None when unknown/not given)."""
    if ram is None:
        return None
    best = None
    for t in _TIERS:
        if ram >= t:
            best = t
    return best


def tier_auto():
    """tier() with on-device RAM detection."""
    return tier(ram_gb())


def resident_gb(params_b):
    """Estimated model resident RAM: fp16 embed + KV + one layer."""
    return round(params_b * 0.35 + 0.35, 2)


def fits(params_b, ram=None, headroom_gb=1.2):
    """Does a model of params_b fit in the available RAM?"""
    ram = ram if ram is not None else ram_gb()
    if ram is None:
        return False
    return resident_gb(params_b) <= ram - headroom_gb
