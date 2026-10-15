"""Exhaustive finite option matrices with mocked media and ASR (no network).

This tests application behavior, not recognition accuracy. All real exports are
written in a TemporaryDirectory and read back. Each failing case reports options.
"""
import csv
import itertools
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import ANY, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import tiktok_core as core
from localization import catalogs
from model_benchmark import save, WORK

IDS = [str(7450000000000000000 + n) for n in range(3)]
VIDEOS = [{"id": vid, "title": f"Vídeo {n} — 日本語; \"titolo\"\nsecond line",
           "duration": 81, "timestamp": 1754300000,
           "url": f"https://www.tiktok.com/@matrix/video/{vid}", "handle": "matrix"}
          for n, vid in enumerate(IDS)]
INFO = {"uploader": "matrix", "duration": 81, "timestamp": 1754300000}
SPEECH = [{"start": 1, "end": 4, "text": "Ciao mondo. 日本語 العربية हिन्दी"},
          {"start": 65, "end": 70, "text": "Seconda frase, con accenti: perché?"}]


class FakeEngine:
    workers = 2

    def __init__(self, name):
        self.name = name
        self.calls = []

    def transcribe(self, path, language=None):
        self.calls.append(language)
        # The first two fake videos are English, the last is Italian. Auto
        # must continue to detect later clips rather than remember English.
        detected = "it" if path == IDS[-1] else "en"
        return SPEECH, {"language": language or detected, "confidence": 0.99}


def exports(base):
    count = 0
    spoken = " ".join(x["text"] for x in SPEECH)
    folder = base / "exports"
    folder.mkdir()
    # Every UI locale × speech language × model × format × timestamps ×
    # speech/silence/long text. Model does not transform the original text.
    for ui, language, model, fmt, stamps, kind in itertools.product(
            catalogs(), core.LANGUAGES, core.MODELS, ("md", "txt"), (False, True), ("speech", "silence", "long")):
        context = (ui, language, model, fmt, stamps, kind)
        lines = [] if kind == "silence" else SPEECH if kind == "speech" else SPEECH * 12
        expected = " ".join(x["text"] for x in lines)
        meta = {"language": language if language != "auto" else "it", "confidence": 0.91}
        row = core.write_transcript(str(folder), VIDEOS[0], INFO, lines, meta, fmt, stamps, ui)
        header, body = core._read_transcript(row["path"])
        assert " ".join(body.split()) == expected, context
        assert header["language"] == meta["language"] and header["duration"] == "81", context
        assert header["date"] == core._date(INFO["timestamp"]) and header["url"] == VIDEOS[0]["url"], context
        text = Path(row["path"]).read_text(encoding="utf-8")
        assert "\ufffd" not in text and "\r" not in text, context
        assert ("[1:05]" in text) == bool(stamps and lines), context
        assert len(core.transcripts_on_disk(folder)) == 1, context
        count += 1
    # Gallery-like rebuild without fresh metadata must work for both formats.
    for path in folder.iterdir():
        path.unlink()
    for fmt in ("md", "txt"):
        video = {**VIDEOS[0], "title": "# Hashtag originale"}
        row = core.write_transcript(folder, video, INFO, SPEECH, {"language": "it"}, fmt)
        assert core._read_transcript(row["path"])[0]["title"] == video["title"]
        Path(row["path"]).unlink()
    for fmt in ("txt", "md"):
        for i, ui in enumerate(catalogs()):
            video = {**VIDEOS[i % 3], "id": str(7460000000000000000 + i)}
            core.write_transcript(folder, video, INFO, SPEECH, {"language": "it", "confidence": 0.9}, fmt, True, ui)
        core.rebuild_collection(folder, "matrix", ui_language="it")
        with (folder / "_index @matrix.csv").open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f, delimiter=";"))
        assert len(rows) == 14 and all(r["language"] == "it" and r["duration_s"] == "81" for r in rows), rows
        assert [int(r["id"]) for r in rows] == sorted([int(r["id"]) for r in rows], reverse=True)
        assert (folder / "_ALL @matrix.md").read_text(encoding="utf-8").count("Ciao mondo") == 14
    # Redo a gallery transcript in a different language. An existing CSV must
    # not win over the new file's metadata, including an explicitly empty value.
    video = {**VIDEOS[0], "id": str(7460000000000000000)}
    for detected, lines in (("fr", SPEECH), ("", [])):
        core.write_transcript(folder, video, INFO, lines, {"language": detected, "confidence": 0.9}, "txt", False, "fr")
        core.rebuild_collection(folder, "matrix")
        with (folder / "_index @matrix.csv").open(encoding="utf-8-sig", newline="") as f:
            row = next(r for r in csv.DictReader(f, delimiter=";") if r["id"] == video["id"])
        assert row["language"] == detected, row
    return count


def pipeline(base):
    count = 0

    def listing(url, browser=None, limit=None, video_link=None, log=None):
        yield {"handle": "matrix", "id": "public"}
        videos = VIDEOS[:1] if video_link else VIDEOS
        yield from videos[:limit] if limit else videos

    def download(video, tmp, browser, on_progress=None, cancelled=None):
        return video["id"], {**INFO, "webpage_url": video["url"]}

    with patch.object(core, "iter_profile", listing), patch.object(core, "download_clip", download), \
         patch.object(core, "whisper_installed", return_value=True):
        for model, language, fmt, stamps, resume, limit, source in itertools.product(
                core.MODELS, core.LANGUAGES, ("md", "txt"), (False, True), (False, True),
                (1, 2, None), ("@matrix", "https://www.tiktok.com/@matrix", VIDEOS[0]["url"])):
            options = {"model": model, "language": language, "format": fmt, "timestamps": stamps,
                       "resume": resume, "limit": limit, "profile": source, "folder": str(base / "pipeline")}
            folder = Path(core.profile_folder(options["folder"], "matrix"))
            folder.mkdir(parents=True, exist_ok=True)
            for path in folder.iterdir():
                path.unlink()
            # Resume sees the first video, even when changing format/model.
            original = core.write_transcript(folder, VIDEOS[0], INFO, SPEECH,
                                              {"language": "en", "confidence": 0.9}, "md")
            events, engine = [], FakeEngine(model)
            job = core.Transcriber(options, events.append, engine=lambda log: engine)
            job.run()
            finished = next(e for e in reversed(events) if e["type"] == "finished")
            total = 1 if "/video/" in source else limit or 3
            assert finished["errors"] == 0 and finished["ok"] == total - int(resume), (options, finished, events)
            assert finished["skipped"] == int(resume), (options, finished)
            assert len(core.transcripts_on_disk(folder)) == total, options
            expected_language = None if language == "auto" else language
            assert engine.calls == [expected_language] * (total - int(resume)), (options, engine.calls)
            for row in job.results.values():
                assert Path(row["path"]).suffix == "." + fmt and row["text"], options
            if resume:
                assert Path(original["path"]).exists(), options
            assert not any(e.get("level") == "err" for e in events), (options, events)
            count += 1
            if count % 540 == 0:
                print("PIPELINE", count, flush=True)
    return count


def engine_contract():
    # Verify each real Engine receives per-video auto/forced options and keeps
    # the hallucination protections, without using a model or GPU here.
    from types import SimpleNamespace
    engine = core.Engine.__new__(core.Engine)
    calls = []

    class Model:
        def transcribe(self, path, **kwargs):
            calls.append(kwargs)
            segments = [] if path == "silence" else [SimpleNamespace(start=0, end=1, text="Ciao mondo")]
            return iter(segments), SimpleNamespace(language="it", language_probability=0.94)

    engine.m = Model()
    for language in core.LANGUAGES:
        _, meta = engine.transcribe("speech", language)
        assert calls[-1]["language"] == (None if language == "auto" else language)
        assert calls[-1]["vad_filter"] and not calls[-1]["condition_on_previous_text"]
        assert calls[-1]["vad_parameters"]["min_speech_duration_ms"] == 100
        assert meta["language"] == "it"
        assert (meta["confidence"] is None) == (language != "auto")
    assert engine.transcribe("silence")[1] == {"language": "", "confidence": 0}
    assert core.model_name("unknown") == core.DEFAULT_MODEL
    with tempfile.TemporaryDirectory(prefix="model_cache_contract_") as directory:
        for name, model in core.MODELS.items():
            if name == "qwen3-asr":
                main, language = Path(directory) / "qwen.gguf", Path(directory) / "lid.gguf"
                with patch.object(core, "natural_model_files", return_value=[str(main), str(language)]), \
                     patch.dict(model, {"bytes": 7}), patch.dict(core.LANGUAGE_MODEL, {"bytes": 7}):
                    assert not core.model_downloaded(name)
                    main.write_bytes(b"fixture")
                    assert not core.model_downloaded(name), "Missing language detector reported ready"
                    language.write_bytes(b"fixture")
                    assert core.model_downloaded(name)
                    main.write_bytes(b"fixtur")
                    assert not core.model_downloaded(name), "Truncated model reported ready"
                continue
            folder = Path(directory) / "snapshots" / model["revision"]
            folder.mkdir(parents=True)
            with patch.object(core, "_model_folder", return_value=directory):
                assert not core.model_downloaded(name)
                for filename in ("model.bin", "config.json", "tokenizer.json"):
                    (folder / filename).write_bytes(b"fixture")
                assert not core.model_downloaded(name), "Missing vocabulary was reported ready"
                (folder / "vocabulary.txt").write_bytes(b"fixture")
                assert core.model_downloaded(name)
                (folder / "tokenizer.json").write_bytes(b"")
                assert not core.model_downloaded(name), "Empty tokenizer was reported ready"
    import faster_whisper.utils
    for name, model in core.MODELS.items():
        if name == "qwen3-asr":
            with patch("huggingface_hub.hf_hub_download") as fetch:
                core.download_model(name)
            assert fetch.call_count == 2
            for call, source in zip(fetch.call_args_list, (model, core.LANGUAGE_MODEL)):
                assert call.args == (source["repo"], source["filename"])
                assert call.kwargs == {"revision": source["revision"], "token": False}
            continue
        with patch.object(faster_whisper.utils, "download_model") as fetch:
            core.download_model(name)
        fetch.assert_called_once_with(model["repo"], revision=model["revision"], use_auth_token=False)
    # GPU inference can fail AFTER the weights loaded. Check the automatic CPU
    # fallback for every shipped model, without needing to break the real GPU.
    import faster_whisper
    for name in core.MODELS:
        if name == "qwen3-asr":
            with patch.object(core, "ensure_ready"), patch("natural_asr.NaturalEngine") as factory:
                factory.return_value.device = "cpu"
                factory.return_value.compute = "Q8_0"
                factory.return_value.workers = 1
                factory.return_value.transcribe.return_value = ([], {"language": "", "confidence": 0})
                natural = core.Engine(name, log=lambda *a: None)
                assert natural.device == "cpu" and natural.workers == 1
                assert natural.transcribe("silence") == ([], {"language": "", "confidence": 0})
                factory.assert_called_once_with(*core.natural_model_files(), log=ANY)
            continue
        builds = []

        class FallbackModel:
            def __init__(self, selected, **kwargs):
                builds.append((selected, kwargs))

            def transcribe(self, *args, **kwargs):
                raise RuntimeError("simulated missing CUDA library at inference")

        with patch.object(core, "ensure_ready"), patch.object(core, "gpu_available", return_value=(True, "ready")), \
             patch.object(faster_whisper, "WhisperModel", FallbackModel):
            fallback = core.Engine(name, log=lambda *a: None)
        assert fallback.device == "cpu" and fallback.compute == "int8"
        assert [b[0] for b in builds] == [core._model_snapshot(name)] * 2
        assert builds[1][1]["device"] == "cpu" and builds[1][1]["compute_type"] == "int8"
    return len(calls) + 1 + len(core.MODELS) * 6


if __name__ == "__main__":
    begin = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="model_matrix_") as temporary:
        base = Path(temporary)
        report = {"network": False, "asr": "mocked", "export_cases": exports(base),
                  "pipeline_cases": pipeline(base), "engine_contract_cases": engine_contract()}
    report["seconds"] = round(time.monotonic() - begin, 2)
    report["passed"] = True
    save(WORK / "matrix.json", report)
    print("PASS", report, flush=True)
