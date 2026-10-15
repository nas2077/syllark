"""Reproducible local ASR comparison. Downloads public FLEURS test samples.

No TikTok credentials, no transcription service. Audio/model downloads are real
network work; inference, language identification and WER/CER are measured locally.
Only the first eight distinct sentences encountered in each test tar are used.
This small diagnostic sample is NOT the published full FLEURS benchmark.
"""
import argparse
import gc
import hashlib
import json
import re
import sys
import tarfile
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import tiktok_core as core

WORK = ROOT / "dev/model-evaluation"
CONFIGS = dict(zip(
    ("it", "en", "es", "fr", "de", "pt", "ru", "ar", "hi", "zh", "ja", "ko", "tr", "id"),
    ("it_it", "en_us", "es_419", "fr_fr", "de_de", "pt_br", "ru_ru", "ar_eg", "hi_in", "cmn_hans_cn", "ja_jp", "ko_kr", "tr_tr", "id_id"),
))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".tmp")
    part.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    part.replace(path)


def prepare_language(item):
    language, config = item
    folder = WORK / "fleurs" / language
    manifest = folder / "samples.json"
    if manifest.exists():
        return json.loads(manifest.read_text(encoding="utf-8"))
    folder.mkdir(parents=True, exist_ok=True)
    base = f"https://huggingface.co/datasets/google/fleurs/resolve/main/data/{config}"
    r = requests.get(base + "/test.tsv", timeout=60)
    r.raise_for_status()
    metadata = {p[1]: p for p in (line.split("\t") for line in r.text.splitlines()) if len(p) >= 7}
    samples, sentences = [], set()
    # Stream the archive, stopping after enough distinct sentences. Never extract
    # archive paths: only write a validated WAV basename into our fixture folder.
    with requests.get(base + "/audio/test.tar.gz", stream=True, timeout=(30, 90)) as response:
        response.raise_for_status()
        response.raw.decode_content = True
        with tarfile.open(fileobj=response.raw, mode="r|gz") as archive:
            for member in archive:
                name = Path(member.name).name
                p = metadata.get(name)
                if not member.isfile() or not p or p[0] in sentences:
                    continue
                data = archive.extractfile(member).read()
                target = folder / name
                target.write_bytes(data)
                sentences.add(p[0])
                samples.append({"language": language, "config": config, "sentence_id": p[0],
                                "path": str(target.relative_to(ROOT)), "reference": p[2],
                                "normalized_reference": p[3], "seconds": int(p[5]) / 16000,
                                "speaker_gender": p[6], "sha256": hashlib.sha256(data).hexdigest()})
                if len(samples) == 8:
                    break
    assert len(samples) == 8, (language, len(samples))
    save(manifest, samples)
    print("FIXTURES", language, len(samples), "distinct sentences", flush=True)
    return samples


def normalize(value):
    text = unicodedata.normalize("NFKC", value).casefold()
    return " ".join("".join(c if c.isalnum() or c.isspace() or unicodedata.category(c).startswith("M")
                            else " " for c in text).split())


def distance(reference, hypothesis):
    previous = list(range(len(hypothesis) + 1))
    for i, a in enumerate(reference, 1):
        current = [i]
        for j, b in enumerate(hypothesis, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def score(reference, hypothesis, language):
    a, b = normalize(reference), normalize(hypothesis)
    # Spaces are not word boundaries in Chinese/Japanese. Report CER there;
    # never combine those numbers into a multilingual WER.
    if language in ("zh", "ja"):
        a, b = list(a.replace(" ", "")), list(b.replace(" ", ""))
        metric = "CER"
    else:
        a, b, metric = a.split(), b.split(), "WER"
    return {"metric": metric, "edits": distance(a, b), "reference_units": len(a)}


def benchmark(name, device="cuda", per_language=8, auto_only=False):
    import numpy as np
    from faster_whisper import WhisperModel
    samples = [s for language in CONFIGS for s in json.loads(
        (WORK / "fleurs" / language / "samples.json").read_text(encoding="utf-8"))[:per_language]]
    suffix = f"-sample{per_language}" if per_language != 8 else ""
    report_path = WORK / (name + "-" + device + suffix + ".json")
    report = {"model": name, "device": device, "compute": "float16" if device == "cuda" else "int8",
              "method": f"{per_language} distinct test sentences per language; application VAD/decoding",
              "samples": [], "silence": [], "summary": []}
    begin = time.perf_counter()
    engine = core.Engine.__new__(core.Engine)
    engine.name, engine.device = name, device
    if name == "qwen3-asr":
        from natural_asr import NaturalEngine
        engine._natural = NaturalEngine(*core.natural_model_files(), log=lambda *a: None,
                                        backend="cpu" if device == "cpu" else "auto")
        engine.device = device = engine._natural.device
        report["device"], report["compute"] = device, "Q8_0"
        report_path = WORK / (name + "-" + device + suffix + ".json")
    else:
        engine.m = WhisperModel(core._model_snapshot(name), device=device, compute_type=report["compute"],
                                cpu_threads=8, num_workers=1)
        engine._smoke_test()
    report["load_seconds"] = round(time.perf_counter() - begin, 3)
    for sample in samples:
        for mode in (("auto",) if auto_only else ("auto", "forced")):
            start = time.perf_counter()
            lines, meta = engine.transcribe(str(ROOT / sample["path"]),
                                           sample["language"] if mode == "forced" else None)
            text = " ".join(line["text"] for line in lines)
            report["samples"].append({**sample, "expected_language": sample["language"],
                                       "mode": mode, "text": text, **meta,
                                       "inference_seconds": round(time.perf_counter() - start, 4),
                                       **score(sample["reference"], text, sample["language"])})
        if sample == next((s for s in reversed(samples) if s["language"] == sample["language"]), None):
            print("BENCH", name, device, sample["language"], flush=True)
            save(report_path, report)
    for seconds in (1, 5, 30, 65):
        lines, meta = engine.transcribe(np.zeros(16000 * seconds, dtype=np.float32))
        report["silence"].append({"seconds": seconds, "text": " ".join(x["text"] for x in lines), **meta})
        assert not lines, (name, seconds, lines)
    for language in CONFIGS:
        for mode in ("auto", "forced"):
            rows = [r for r in report["samples"] if r["expected_language"] == language and r["mode"] == mode]
            # Detected language is kept separately below: meta.language may
            # differ from the fixture's expected language.
            if not rows:
                continue
            report["summary"].append({"language": language, "mode": mode, "samples": len(rows),
                                      "metric": rows[0]["metric"],
                                      "language_correct": sum(r["language"] == language for r in rows),
                                      "error_percent": round(100 * sum(r["edits"] for r in rows) /
                                                             sum(r["reference_units"] for r in rows), 2),
                                      "inference_seconds": round(sum(r["inference_seconds"] for r in rows), 3),
                                      "audio_seconds": round(sum(r["seconds"] for r in rows), 2)})
    if per_language == 8:
        stress_cases(engine, report, samples)
    save(report_path, report)
    del engine
    gc.collect()
    print("SAVED", report_path.name, flush=True)


def stress_cases(engine, report, samples):
    import numpy as np
    report["stress"] = []
    report["silence"] = [r for r in report["silence"] if "kind" not in r]
    from faster_whisper.audio import decode_audio
    rng = np.random.default_rng(20261015)
    for language in CONFIGS:
        sample = next(s for s in samples if s["language"] == language)
        waveform = decode_audio(str(ROOT / sample["path"]), sampling_rate=16000)
        for condition in ("noise_10db", "padded_silence"):
            if condition == "noise_10db":
                noise = rng.normal(size=len(waveform)).astype(np.float32)
                noise *= np.sqrt(np.mean(waveform ** 2) / (10 * np.mean(noise ** 2)))
                audio = np.clip(waveform + noise, -1, 1)
            else:
                audio = np.concatenate([np.zeros(16000 * 12, np.float32), waveform,
                                        np.zeros(16000 * 15, np.float32)])
            start = time.perf_counter()
            lines, meta = engine.transcribe(audio)
            text = " ".join(line["text"] for line in lines)
            report["stress"].append({"expected_language": language, "condition": condition,
                                      "text": text, **meta, **score(sample["reference"], text, language),
                                      "inference_seconds": round(time.perf_counter() - start, 4)})
    for kind, waveform in (
        ("white_noise", rng.normal(0, 0.03, 16000 * 15).astype(np.float32)),
        ("tones", (0.04 * np.sin(2 * np.pi * 440 * np.arange(16000 * 15) / 16000) +
                   0.03 * np.sin(2 * np.pi * 660 * np.arange(16000 * 15) / 16000)).astype(np.float32)),
    ):
        lines, meta = engine.transcribe(waveform)
        report["silence"].append({"kind": kind, "seconds": 15,
                                   "text": " ".join(x["text"] for x in lines), **meta})


def stress_existing(name):
    path = WORK / (name + "-cuda.json")
    report = json.loads(path.read_text(encoding="utf-8"))
    engine = core.Engine(name, log=lambda *args: None)
    samples = [s for language in CONFIGS for s in json.loads(
        (WORK / "fleurs" / language / "samples.json").read_text(encoding="utf-8"))]
    stress_cases(engine, report, samples)
    save(path, report)
    print("STRESS SAVED", name, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run", "stress"))
    parser.add_argument("--model", default="large-v3-turbo")
    parser.add_argument("--device", default="cuda", choices=("cuda", "cpu"))
    parser.add_argument("--per-language", type=int, default=8)
    parser.add_argument("--auto-only", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(prepare_language, CONFIGS.items()))
    elif args.action == "stress":
        stress_existing(args.model)
    else:
        benchmark(args.model, args.device, args.per_language, args.auto_only)
