"""Transcription: whisper CLI when installed; SRT/VTT passthrough otherwise.

Offline-first: whisper.cpp / openai-whisper on-device. When neither exists,
reuse an existing subtitle file (SRT/VTT) so the rest of the pipeline still
works.
"""
import os
import subprocess
import shutil

WHISPER = shutil.which("whisper")


def transcribe(audio_path, out_dir, model="small", language=None):
    """audio -> out_dir/transcript.srt (whisper CLI required)."""
    os.makedirs(out_dir, exist_ok=True)
    if not WHISPER:
        raise RuntimeError("whisper CLI not installed")
    cmd = [WHISPER, audio_path, "--model", model, "--output_format", "srt",
           "--output_dir", out_dir]
    if language:
        cmd += ["--language", language]
    subprocess.run(cmd, check=True)
    srt = os.path.join(out_dir, os.path.splitext(os.path.basename(audio_path))[0] + ".srt")
    return srt if os.path.exists(srt) else _find_srt(out_dir)


def _find_srt(out_dir):
    for f in os.listdir(out_dir):
        if f.endswith(".srt"):
            return os.path.join(out_dir, f)
    raise RuntimeError("no srt produced")


def srt_to_vtt(path, out=None):
    """Re-format an SRT file as WebVTT (handy for clip-factory captions)."""
    out = out or path.rsplit(".", 1)[0] + ".vtt"
    with open(path, encoding="utf-8") as f:
        text = f.read()
    lines = ["WEBVTT", ""]
    for block in text.strip().split("\n\n"):
        parts = block.splitlines()
        if len(parts) < 2:
            continue
        timing = parts[1].replace(",", ".")
        lines.append(timing)
        lines.extend(parts[2:])
        lines.append("")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out
