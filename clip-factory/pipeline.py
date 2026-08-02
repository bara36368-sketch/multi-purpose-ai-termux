"""clip-factory pipeline: script -> edit plan -> SRT -> captions -> draft.

Offline by default (writes a local draft manifest + SRT); pass
--vectcut-url/--vectcut-key to push materials to the VectCut cloud API.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from director import PLATFORMS, plan  # noqa: E402
from subtitles import write_srt  # noqa: E402
from vectcut import OfflineVectCut, VectCut  # noqa: E402


def run(script, platform, out_dir, style, vectcut_url=None, vectcut_key=None,
        draft_name="clip-factory"):
    os.makedirs(out_dir, exist_ok=True)
    p = plan(script, platform=platform, style=style)

    srt_path = os.path.join(out_dir, "captions.srt")
    cues = [{"start_ms": c["start_ms"], "end_ms": c["end_ms"], "text": c["text"]}
            for c in p["captions"]]
    write_srt(cues, srt_path)

    if vectcut_url:
        vc = VectCut(vectcut_url, vectcut_key)
        draft = vc.create_draft(draft_name, aspect=p["aspect"])
        for c in p["captions"]:
            vc.add_caption_material(draft["id"], c["text"], c["start_ms"],
                                    c["end_ms"], style=c["emphasis"])
        result = vc.export(draft["id"])
    else:
        vc = OfflineVectCut(out_dir)
        draft = vc.create_draft(draft_name, aspect=p["aspect"])
        for c in p["captions"]:
            vc.add_caption_material(draft["id"], c["text"], c["start_ms"],
                                    c["end_ms"], style=c["emphasis"])
        result = vc.export(draft["id"])

    return {"plan": p, "srt": srt_path, "draft": result,
            "mode": "vectcut" if vectcut_url else "offline"}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="clip-factory", description=__doc__)
    ap.add_argument("script", help="script text file or inline string")
    ap.add_argument("--platform", choices=list(PLATFORMS), default="shorts")
    ap.add_argument("--style", default="energetic")
    ap.add_argument("--out", default="out")
    ap.add_argument("--vectcut-url")
    ap.add_argument("--vectcut-key")
    args = ap.parse_args(argv)

    if os.path.isfile(args.script):
        with open(args.script, encoding="utf-8") as f:
            script = f.read()
    else:
        script = args.script

    r = run(script, args.platform, args.out, args.style,
            args.vectcut_url, args.vectcut_key)
    print(f"platform={r['plan']['platform']} beats={len(r['plan']['beats'])} "
          f"captions={len(r['plan']['captions'])} total_ms={r['plan']['total_ms']}")
    print(f"srt:      {r['srt']}")
    print(f"draft:    {r['draft'].get('path', r['draft'])} (mode={r['mode']})")


if __name__ == "__main__":
    main()
