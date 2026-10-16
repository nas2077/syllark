"""Offline OS boundary and archive regressions, runnable on every CI host."""
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import desktop_platform as desktop
from package_release import package


class Platforms(unittest.TestCase):
    def test_data_paths_are_outside_the_install(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(Path, "home", return_value=Path(temporary)):
            for system, suffix in (("darwin", "Library/Application Support/Syllark"),
                                   ("linux", ".local/share/syllark"),
                                   ("win32", "AppData/Local/TikTok Transcriber")):
                with self.subTest(system=system), patch.object(sys, "platform", system), patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(desktop.user_data_dir(), Path(temporary) / suffix)
            with patch.object(sys, "platform", "linux"), patch.dict(os.environ, {"XDG_DATA_HOME": temporary}):
                self.assertEqual(desktop.user_data_dir(), Path(temporary) / "syllark")

    def test_opening_paths_uses_argument_lists(self):
        with patch.object(desktop.subprocess, "Popen") as popen:
            for system, command in (("darwin", "open"), ("linux", "xdg-open")):
                with patch.object(sys, "platform", system):
                    desktop.open_path("a folder; $(literal)")
                    self.assertEqual(popen.call_args.args[0], [command, os.path.abspath("a folder; $(literal)")])
                    self.assertNotIn("shell", popen.call_args.kwargs)

    def test_linux_documents_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary)
            (config / "user-dirs.dirs").write_text('XDG_DOCUMENTS_DIR="$HOME/Documenti"\n', encoding="utf-8")
            with patch.object(sys, "platform", "linux"), patch.object(Path, "home", return_value=config), patch.dict(os.environ, {"XDG_CONFIG_HOME": temporary}):
                self.assertEqual(Path(desktop.documents_dir()), config / "Documenti")

    def test_system_language_and_renderer(self):
        with patch.object(sys, "platform", "linux"), patch.dict(os.environ, {"LANGUAGE": "it_IT:en", "QT_API": "pyside6"}):
            self.assertEqual(desktop.system_language(), "it_IT")
            self.assertEqual(desktop.webview_gui(), "qt")
        with patch.object(sys, "platform", "darwin"):
            self.assertEqual(desktop.webview_gui(), "cocoa")

    def test_natural_reports_the_platform_gpu_backend(self):
        import tiktok_core as core
        for system, backend in (("darwin", "metal"), ("linux", "vulkan"), ("win32", "vulkan")):
            requested = []
            native = SimpleNamespace(backend_available=lambda name: requested.append(name) or True)
            with patch.object(sys, "platform", system), patch.dict(sys.modules, {"transcribe_cpp": native}):
                self.assertEqual(core.gpu_available("qwen3-asr"), (True, backend.title()))
                self.assertEqual(requested, [backend])

    def test_unix_never_downloads_windows_cuda_wheels(self):
        import tiktok_core as core
        for system in ("darwin", "linux"):
            with patch.object(sys, "platform", system), patch.object(core, "model_downloaded", return_value=True), \
                 patch.object(core, "nvidia_card") as card, patch.object(core, "install_cuda") as install:
                core.ensure_ready("small")
                install.assert_not_called()
                card.assert_not_called()

    def test_unix_archive_keeps_executable_mode_and_excludes_user_data(self):
        if os.name == "nt":
            self.skipTest("Unix permissions are tested on Linux/macOS CI")
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "Syllark"
            runtime = folder / "runtime"
            runtime.mkdir(parents=True)
            binary = folder / "Syllark"
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o755)
            (runtime / "ui.html").write_text("app")
            (folder / "settings.json").write_text("private")
            (runtime / "link").symlink_to("ui.html")
            archive = Path(temporary) / "app.tar.gz"
            package(folder, archive, system="linux")
            with tarfile.open(archive) as bundle:
                self.assertTrue(bundle.getmember("Syllark/Syllark").mode & 0o111)
                self.assertTrue(bundle.getmember("Syllark/runtime/link").issym())
                self.assertNotIn("Syllark/settings.json", bundle.getnames())
            (runtime / "outside").symlink_to(Path(temporary))
            with self.assertRaises(ValueError):
                package(folder, archive, system="linux")

    def test_single_instance_is_released_on_exit(self):
        if os.name == "nt":
            self.skipTest("Unix advisory locks")
        with tempfile.TemporaryDirectory() as temporary:
            code = "import desktop_platform as d,sys; print(d.unix_already_running(sys.argv[1]))"
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            self.assertFalse(desktop.unix_already_running(temporary))
            try:
                self.assertEqual(subprocess.check_output([sys.executable, "-c", code, temporary], env=env).strip(), b"True")
            finally:
                desktop._instance_lock.close()
                desktop._instance_lock = None
            self.assertEqual(subprocess.check_output([sys.executable, "-c", code, temporary], env=env).strip(), b"False")


if __name__ == "__main__":
    unittest.main(verbosity=2)
