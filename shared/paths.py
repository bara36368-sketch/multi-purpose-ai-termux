"""Path resolution for the cyberdeck stack.

Mirrors androidllm_models.py: the androidllm dir, model shard dirs, and
state files live under ~/androidllm by default, overridable with
ANDROIDLLM_DIR.
"""
import os

_HOME = os.path.expanduser("~")


def androidllm_dir(env=None):
    env = env if env is not None else os.environ
    return env.get("ANDROIDLLM_DIR", os.path.join(_HOME, "androidllm"))


def models_dir(env=None):
    return os.path.join(androidllm_dir(env), "models")


def shard_dir(model_id, env=None):
    return os.path.join(models_dir(env), model_id)


def state_path(env=None):
    return os.path.join(androidllm_dir(env), "current_model.json")


def api_key_path(env=None):
    return os.path.join(androidllm_dir(env), "api_key")


def read_api_key(env=None):
    """The persisted server API key, or None when missing/too short."""
    p = api_key_path(env)
    try:
        with open(p, encoding="utf-8") as f:
            key = f.read().strip()
        return key if len(key) >= 16 else None
    except OSError:
        return None
