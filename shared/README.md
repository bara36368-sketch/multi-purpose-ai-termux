# shared

Stdlib-only helpers shared across modules. Nothing here may import from
modules — modules import from `shared`, never the reverse.

Planned helpers:
- `paths.py` — androidllm dir / state file resolution (mirrors
  `androidllm_models.py`)
- `atomic_json.py` — atomic read/write of JSON state files
- `mem.py` — RAM tier detection (`/proc/meminfo` → 5/6/7/8/9/10/12/16 GB tier)
