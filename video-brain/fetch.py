"""Fetch video + audio: yt-dlp when available, direct URL fallback."""
import os
import shutil
import subprocess

YTDLP = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
FFMPEG = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
FFPROBE = shutil.which("ffprobe") or shutil.which("ffprobe.exe")


def has_ytdlp():
    return YTDLP is not None


def has_ffmpeg():
    return FFMPEG is not None


def fetch_audio(url, out_dir, name="audio"):
    """Download best audio stream to out_dir/audio.m4a (yt-dlp required)."""
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, name)
    if not YTDLP:
        raise RuntimeError("yt-dlp not installed: pip install yt-dlp")
    subprocess.run([YTDLP, "-x", "--audio-format", "m4a", "-o", out + ".%(ext)s",
                    "--no-playlist", "--quiet", url], check=True)
    for f in os.listdir(out_dir):
        if f.startswith(name) and f.endswith(".m4a"):
            return os.path.join(out_dir, f)
    raise RuntimeError("yt-dlp produced no audio file")


def duration_ms(path):
    """Duration via ffprobe, or None when unavailable."""
    if not FFPROBE:
        return None
    r = subprocess.run([FFPROBE, "-v", "quiet", "-show_entries",
                        "format=duration", "-of", "json", path],
                       capture_output=True, text=True)
    import json
    try:
        return int(float(json.loads(r.stdout)["format"]["duration"]) * 1000)
    except Exception:
        return None
