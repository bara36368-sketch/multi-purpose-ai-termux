"""Per-tool permissions. Nothing is exposed by default."""
import json
import os

DEFAULT_PERMS = {
    "allowed": ["battery", "thermal", "device_info"],
    "denied": [],
}


def load_permissions(path=None):
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "permissions.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data.get("allowed"), list) and isinstance(data.get("denied"), list):
            return data
    except Exception:
        pass
    return dict(DEFAULT_PERMS)


def is_allowed(perms, tool):
    if tool in perms.get("denied", []):
        return False
    return tool in perms.get("allowed", [])
