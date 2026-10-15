"""Offline invariants for readable exports, legacy files and collection rebuilds."""
import itertools
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import tiktok_core as core
from localization import catalogs


def flat(text):
    return " ".join(text.split())


sentences = [
    "Questo è un esempio abbastanza lungo: parla di un iPhone 18 Pro, del prezzo di 1.299,90 € e delle sue caratteristiche.",
    "L'idea è conservare esattamente parole, accenti, nomi e numeri: nessuna riscrittura, nessuna promessa di accuratezza perfetta.",
    "Qui c'è una domanda utile: funziona anche senza connessione? Ecco come puoi verificarlo sul tuo computer.",
    "Il video continua con una nuova spiegazione e una frase completa, così possiamo controllare la divisione dei paragrafi.",
    "Arriviamo infine all'ultimo punto, che deve comparire anche nella raccolta del profilo e quando riprendiamo un lavoro.",
    "Grazie per aver seguito questa prova: tutte le parole devono rimanere nell'ordine originale, compresa quest'ultima frase.",
]
lines = [{"start": i * 8, "end": i * 8 + 7.8, "text": text} for i, text in enumerate(sentences)]
expected = " ".join(sentences)
formatted = core.readable_text(lines)
assert flat(formatted) == expected and len(formatted.split("\n\n")) >= 2
# A single long ASR segment also needs paragraphs at existing sentence endings.
assert "\n\n" in core.readable_text([{"text": expected}])
# A clear pause is usable even when recognition supplied no punctuation.
raw = [{"start": 0, "end": 10, "text": "parlato senza punteggiatura " * 10},
       {"start": 12, "end": 18, "text": "una nuova parte dopo la pausa"}]
assert "\n\n" in core.readable_text(raw)
assert flat(core.readable_text(raw)) == flat(" ".join(x["text"] for x in raw))
assert core.readable_text([]) == ""

checks = 5
with tempfile.TemporaryDirectory(prefix="readability_") as temp:
    folder = Path(temp)
    for locale, fmt, stamps in itertools.product(catalogs(), ("md", "txt"), (False, True)):
        video = {"id": "7690990716016741665", "title": "Prova: iPhone e punteggiatura", "handle": "readability",
                 "url": "https://www.tiktok.com/@readability/video/7690990716016741665"}
        row = core.write_transcript(folder, video, {"duration": 48}, lines, {"language": "it"}, fmt, stamps, locale)
        header, body = core._read_transcript(row["path"])
        assert flat(body) == expected, (locale, fmt, stamps)
        assert "\n\n" in body, (locale, fmt, stamps, body)
        assert flat(row["text"]) == expected and row["words"] == len(expected.split())
        assert core.rebuild_collection(folder, "readability", ui_language=locale) == 1
        collection = (folder / "_ALL @readability.md").read_text(encoding="utf-8")
        assert body in collection
        # Repeat from disk alone, including a source-app restart/resume.
        assert core.rebuild_collection(folder, "readability", ui_language=locale) == 1
        assert body in (folder / "_ALL @readability.md").read_text(encoding="utf-8")
        checks += 1
    for fmt, stamps in itertools.product(("md", "txt"), (False, True)):
        row = core.write_transcript(folder, video, {}, raw, {"language": "it"}, fmt, stamps)
        body = core._read_transcript(row["path"])[1]
        assert body == core.readable_text(raw), (fmt, stamps, body)
        core.rebuild_collection(folder, "readability")
        assert body in (folder / "_ALL @readability.md").read_text(encoding="utf-8")
        checks += 1
    # User-authored line wrapping and explicit paragraph breaks remain intact.
    path = folder / "legacy.txt"
    path.write_text("Old\n------------------------------\n\nFirst line\nwrapped here.\n\nAnother paragraph.\n", encoding="utf-8")
    assert core._read_transcript(path)[1] == "First line wrapped here.\n\nAnother paragraph."
    checks += 1
    # Every script/case/number survives formatting, including combining marks.
    for text in ("中文。下一句？", "日本語です。次の文。", "العربية؟ نعم، صحيح.", "हिन्दी है। ठीक है।",
                 "iPhone 18, Wi-Fi 7, U.S.A., 6,83 pollici, 67 W, 8340 mAh.", "cafe\u0301 perché не терять 한국어"):
        assert flat(core.readable_text([{"text": text}] * 15)) == flat(" ".join([text] * 15))
        checks += 1

report = {"offline": True, "checks": checks, "export_combinations": 56,
          "validated": ["word/case/number order", "sentence and audio-pause paragraphs", "single long segment",
                        "14 locales x MD/TXT x timestamps", "collections and resume", "legacy wrapped text", "Unicode"]}
target = ROOT / "dev/speech-quality/readability-check.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("PASS", checks, "readability checks")
