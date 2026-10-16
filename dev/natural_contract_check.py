"""Offline regressions for native fallback, cancellation, boundaries and caches."""
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import natural_asr as natural


class BackendFailure(RuntimeError):
    pass


class OutOfMemory(RuntimeError):
    pass


class Aborted(RuntimeError):
    pass


class FakeRuntime:
    BackendError, OutOfMemory, Aborted = BackendFailure, OutOfMemory, Aborted

    def __init__(self, load_failure=False, inference_failure=False):
        self.models = []
        self.load_failure, self.inference_failure = load_failure, inference_failure

    def Model(self, path, backend):
        if path == "asr" and backend == "auto" and self.load_failure:
            raise BackendFailure("simulated GPU initialization failure")
        model = SimpleNamespace(device=SimpleNamespace(kind="cpu" if backend == "cpu" else "vulkan"),
                                capabilities=SimpleNamespace(languages=("it", "en")), closed=False,
                                calls=0, path=path)
        model.close = lambda: setattr(model, "closed", True)

        def run(audio, language=None):
            if not np.any(audio):  # The model's startup smoke test.
                return SimpleNamespace(text="", language="")
            model.calls += 1
            if self.inference_failure and model.device.kind != "cpu" and model.calls == 2:
                raise BackendFailure("simulated GPU inference failure")
            return SimpleNamespace(text="primo" if np.mean(audio) < 1.5 else "secondo", language=language or "it")

        def session(n_threads):
            return SimpleNamespace(run=run, cancel=lambda: None, close=lambda: None)

        model.session = session
        model.langid_session = lambda n_threads: SimpleNamespace(
            run=lambda audio: SimpleNamespace(candidates=(SimpleNamespace(code="it", p=.99),)), close=lambda: None)
        self.models.append(model)
        return model


class NativeContracts(unittest.TestCase):
    def test_model_selection_reports_each_backend_capability(self):
        import app
        import tiktok_core as core
        with tempfile.TemporaryDirectory(prefix="natural_devices_") as directory, \
             patch.object(app, "SETTINGS_FILE", str(Path(directory) / "settings.json")), \
             patch.object(core, "gpu_available", side_effect=lambda name=None: (name == "qwen3-asr", "test")):
            api = app.Api()
            state = api.initial_state()
            self.assertTrue(state["gpu"]["ok"])
            self.assertTrue(all(m["gpu"] == (m["id"] == "qwen3-asr") for m in state["models"]))
            api.save_settings({"whisper_model": "large-v3-turbo"})
            self.assertFalse(api.initial_state()["gpu"]["ok"])

    def test_cpu_information_describes_the_natural_engine(self):
        import app
        import tiktok_core as core
        with tempfile.TemporaryDirectory(prefix="natural_info_") as directory, \
             patch.object(app, "SETTINGS_FILE", str(Path(directory) / "settings.json")), \
             patch.object(core, "gpu_available", return_value=(False, "processor")):
            api = app.Api()
            api.workshop._engine = SimpleNamespace(name="qwen3-asr", device="cpu", workers=1)
            info = api.about()
            self.assertEqual(info["device"], "processor")
            self.assertEqual(info["threads"], 6)
            self.assertEqual(info["transcribers"], 1)

    def test_silence_produces_no_blocks(self):
        self.assertEqual(natural.audio_blocks(np.zeros(16000), []), [])

    def test_original_edge_context_survives(self):
        audio = np.ones(16000 * 5, dtype=np.float32)
        blocks = natural.audio_blocks(audio, [{"start": 8000, "end": 64000}])
        self.assertEqual(blocks, [(0, 80000)])

    def test_real_pause_splits_without_discarding_context(self):
        audio = np.ones(16000 * 10, dtype=np.float32)
        speech = [{"start": 0, "end": 64000}, {"start": 80000, "end": 160000}]
        blocks = natural.audio_blocks(audio, speech)
        self.assertEqual(blocks, [(0, 72000), (72000, 160000)])

    def test_language_boundary_is_contiguous(self):
        audio = np.ones(16000 * 10, dtype=np.float32)
        self.assertEqual(natural.audio_blocks(audio, [{"start": 0, "end": len(audio)}], [80000]),
                         [(0, 80000), (80000, 160000)])

    def test_long_audio_has_bounded_blocks_and_no_lost_samples(self):
        audio = np.ones(16000 * 215, dtype=np.float32)
        blocks = natural.audio_blocks(audio, [{"start": 0, "end": len(audio)}])
        self.assertEqual(blocks[0][0], 0)
        self.assertEqual(blocks[-1][1], len(audio))
        self.assertTrue(all(b - a <= 90 * 16000 for a, b in blocks))
        self.assertTrue(all(x[1] == y[0] for x, y in zip(blocks, blocks[1:])))

    def test_gpu_load_falls_back_to_cpu(self):
        runtime = FakeRuntime(load_failure=True)
        with patch.object(natural, "native_runtime", return_value=runtime):
            engine = natural.NaturalEngine("asr", "lid", lambda *a: None)
            self.assertEqual(engine.device, "cpu")
            engine.close()
        self.assertTrue(all(m.closed for m in runtime.models))

    def test_inference_fallback_restarts_without_duplicate_partial_text(self):
        runtime = FakeRuntime(inference_failure=True)
        audio = np.concatenate((np.ones(64000), np.zeros(64000), np.ones(64000) * 2)).astype(np.float32)
        speech = [{"start": 0, "end": 64000}, {"start": 128000, "end": len(audio)}]
        with patch.object(natural, "native_runtime", return_value=runtime), \
             patch("faster_whisper.vad.get_speech_timestamps", return_value=speech):
            engine = natural.NaturalEngine("asr", "lid", lambda *a: None)
            lines, meta = engine.transcribe(audio, "it")
            self.assertEqual([r["text"] for r in lines], ["primo", "secondo"])
            self.assertEqual(engine.device, "cpu")
            self.assertEqual(meta, {"language": "it", "confidence": None})
            engine.close()
        self.assertTrue(all(m.closed for m in runtime.models))

    def test_cancelled_waiter_does_not_interrupt_active_model(self):
        # Measure lock cancellation, excluding cold native/Python import time.
        from faster_whisper import audio, vad
        runtime = FakeRuntime()
        with patch.object(natural, "native_runtime", return_value=runtime):
            engine = natural.NaturalEngine("asr", "lid", lambda *a: None)
            engine._lock.acquire()
            event = threading.Event()
            timer = threading.Timer(.03, event.set)
            timer.start()
            begin = time.monotonic()
            try:
                with self.assertRaises(natural.TranscriptionCancelled):
                    engine.transcribe(np.ones(16000, dtype=np.float32), "it", event.is_set)
                self.assertLess(time.monotonic() - begin, .4)
            finally:
                engine._lock.release()
                timer.cancel()
                engine.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
