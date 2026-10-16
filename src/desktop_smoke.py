"""Exercise bundled native engines, audio decoding and a real WebView bridge.

No model weights or TikTok requests. Use --ui for the desktop portion.
"""
import argparse
import json
import os
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path


def run(report_path, ui=False):
    progress = Path(report_path).with_suffix(".progress.log")
    def stage(message):
        with progress.open("a", encoding="utf-8") as stream:
            stream.write(message + "\n")
    stage("Importing PyAV")
    import av
    stage("Importing CTranslate2")
    import ctranslate2
    stage("Importing ONNX Runtime")
    import onnxruntime
    stage("Importing transcribe.cpp")
    import transcribe_cpp
    stage("Importing faster-whisper audio")
    from faster_whisper.audio import decode_audio
    stage("Querying native CPU capabilities")

    report = {"platform": sys.platform, "native": transcribe_cpp.native_version(),
              "cpu": transcribe_cpp.backend_available("cpu"),
              "whisper_cpu": sorted(ctranslate2.get_supported_compute_types("cpu")),
              "onnx": onnxruntime.get_available_providers(),
              "ffmpeg": {key: list(value) for key, value in av.library_versions.items()}}
    assert report["cpu"], "Natural CPU backend missing"
    with tempfile.TemporaryDirectory(prefix="syllark-smoke-") as temporary:
        audio = Path(temporary) / "silence.wav"
        with wave.open(str(audio), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16000)
            stream.writeframes(b"\0\0" * 16000)
        assert len(decode_audio(str(audio))) == 16000
        report["audio_decoded"] = True
        if ui:
            stage("Importing app for desktop smoke")
            import app
            failures = []
            completed = threading.Event()
            def verify():
                try:
                    deadline = time.monotonic() + 45
                    while app.window is None and time.monotonic() < deadline:
                        time.sleep(.1)
                    assert app.window is not None, "Window not created"
                    assert app.window.events.loaded.wait(30), "Webview did not load"
                    # This crosses JS -> Python -> JS, not just a static HTML check.
                    app.window.run_js("window.pywebview.api.window_state().then(s=>window.SMOKE_BRIDGE=typeof s.maximized==='boolean')")
                    while time.monotonic() < deadline:
                        if app.window.evaluate_js("window.SMOKE_BRIDGE===true && !!document.querySelector('#w-close')"):
                            report["ui_bridge"] = True
                            break
                        time.sleep(.2)
                    assert report.get("ui_bridge"), "Python/JavaScript bridge did not respond"
                except BaseException as error:
                    failures.append(error)
                finally:
                    completed.set()
                    if app.window:
                        app.window.destroy()
            def watchdog():
                if not completed.wait(60):
                    os._exit(2)
            threading.Thread(target=verify, daemon=True).start()
            threading.Thread(target=watchdog, daemon=True).start()
            stage("Starting desktop event loop")
            app.main()
            if failures:
                raise failures[0]
            assert report.get("ui_bridge"), "Window exited before verification"
    stage("Smoke check completed")
    report["passed"] = True
    Path(report_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PASS: native engines, audio" + (" and desktop bridge" if ui else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    parser.add_argument("--ui", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    run(args.report, args.ui)
