"""Real public profiles, pagination, media/audio and Whisper, without accounts.

Only public requests, a previously cached model and disposable output folders.
Any attempt to read a browser session fails the check immediately.
"""
import json
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import av

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import tiktok_core as core

PROFILES = ("scout2015", "zachking", "khaby.lame", "nasa")


def listing(handle):
    stream = core.iter_profile("https://www.tiktok.com/@" + handle, limit=35)
    head = next(stream)
    videos = list(stream)
    assert head["handle"].casefold() == handle.casefold(), head
    assert len(videos) == 35 and len({v["id"] for v in videos}) == 35, (handle, len(videos))
    print("OK: public profile", handle, "35 unique videos across multiple pages", flush=True)
    return handle, videos


def media(item, work):
    handle, video = item
    folder = work / video["id"]
    folder.mkdir()
    path, info = core.download_clip(video, str(folder), None)
    with av.open(path) as container:
        assert any(s.type == "audio" for s in container.streams), video["id"]
        has_video = any(s.type == "video" for s in container.streams)
    size = Path(path).stat().st_size
    assert size > 1024
    print("OK: public media + audio", handle, video["id"], size, "bytes", "video", has_video, flush=True)
    return {"handle": handle, "id": video["id"], "bytes": size, "video": has_video}


if __name__ == "__main__":
    assert core.model_downloaded(), "This check requires the already-cached default Whisper model"
    report = {"profiles": [], "downloads": [], "jobs": []}
    with tempfile.TemporaryDirectory(prefix="anonymous_matrix_") as output, \
         patch("yt_dlp.cookies.extract_cookies_from_browser", side_effect=AssertionError("browser cookies requested")):
        work = Path(output)
        with ThreadPoolExecutor(max_workers=2) as pool:
            profiles = list(pool.map(listing, PROFILES))
        report["profiles"] = [{"handle": h, "videos": len(v)} for h, v in profiles]
        selected = [(handle, videos[index]) for handle, videos in profiles for index in (0, 16)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            report["downloads"] = list(pool.map(lambda item: media(item, work), selected))

        engine = core.Engine(log=lambda text, level=None: print(text, flush=True))
        for mode, profile, limit in (
            ("profile", "https://www.tiktok.com/@nasa", 2),
            ("single", profiles[1][1][0]["url"], 1),
        ):
            events = []
            job = core.Transcriber({"profile": profile, "folder": str(work / mode),
                                    "ui_language": "it", "limit": limit}, events.append,
                                   engine=lambda log: engine)
            job.run()
            finished = next(e for e in reversed(events) if e["type"] == "finished")
            assert finished["ok"] == limit and finished["errors"] == 0, (mode, finished, events)
            transcripts = core.transcripts_on_disk(finished["folder"])
            assert len(transcripts) == limit
            folder = Path(finished["folder"])
            assert list(folder.glob("_ALL *.md")) and list(folder.glob("_index *.csv"))
            words = sum(row["words"] for row in job.results.values())
            if mode == "profile":
                assert words > 0, "Public speech videos produced no spoken words"
            report["jobs"].append({"mode": mode, "videos": limit, "words": words, "errors": 0})
            print("OK: real Whisper + exports", mode, limit, "videos", words, "words", flush=True)
    (ROOT / "dev" / "anonymous-network-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PASS: 140 listed posts, 8 playable media downloads, 2 real transcription jobs; no browser sessions", flush=True)
