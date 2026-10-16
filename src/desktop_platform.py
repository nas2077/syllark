"""Small OS boundary for the desktop app; imports do not touch native GUIs."""
import locale
import os
import subprocess
import sys
import threading
from pathlib import Path


def user_data_dir():
    home = Path.home()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or home / "AppData/Local") / "TikTok Transcriber"
    if sys.platform == "darwin":
        return home / "Library/Application Support/Syllark"
    base = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
    return (base if base.is_absolute() else home / ".local/share") / "syllark"


def documents_dir():
    if sys.platform == "win32":
        import ctypes
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0 and buffer.value:
            return buffer.value
    elif sys.platform.startswith("linux"):
        # Read XDG's data file without evaluating shell substitutions.
        config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        try:
            for line in (config / "user-dirs.dirs").read_text(encoding="utf-8").splitlines():
                if line.startswith('XDG_DOCUMENTS_DIR="') and line.endswith('"'):
                    value = line.split('"', 2)[1].replace("${HOME}", str(Path.home())).replace("$HOME", str(Path.home()))
                    if "$" not in value and Path(value).is_absolute():
                        return value
        except OSError:
            pass
    return str(Path.home() / "Documents")


def open_path(path):
    path = os.path.abspath(os.fspath(path))
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def system_language():
    if sys.platform == "win32":
        import ctypes
        buffer = ctypes.create_unicode_buffer(85)
        if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):
            return buffer.value
    if sys.platform == "darwin":
        try:
            from Foundation import NSLocale
            return str(NSLocale.preferredLanguages()[0])
        except ImportError:
            pass
    return next((os.environ[k].split(":")[0] for k in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")
                 if os.environ.get(k)), locale.getlocale()[0] or "en")


def webview_gui():
    if sys.platform == "win32":
        return "edgechromium"
    if sys.platform == "darwin":
        return "cocoa"
    os.environ["QT_API"] = "pyside6"
    return "qt"


_awake = threading.local()


def keep_awake(on):
    """Hold a per-worker sleep inhibitor where the desktop provides one."""
    try:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (1 if on else 0))
            return
        process = getattr(_awake, "process", None)
        if on and process is None:
            command = (["caffeinate", "-i", "-w", str(os.getpid())] if sys.platform == "darwin" else
                       ["systemd-inhibit", "--what=sleep", "--mode=block", "--who=Syllark",
                        "--why=Transcribing media", "cat"])
            _awake.process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif not on and process is not None:
            process.stdin.close()
            process.terminate()
            process.wait(timeout=2)
            _awake.process = None
    except (OSError, subprocess.SubprocessError):
        pass


_instance_lock = None


def unix_already_running(folder):
    """Keep the descriptor open for the process lifetime; stale files are harmless."""
    import errno
    import fcntl
    global _instance_lock
    stream = open(Path(folder) / "instance.lock", "a")
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        stream.close()
        if error.errno in (errno.EACCES, errno.EAGAIN):
            return True
        raise
    _instance_lock = stream
    return False
