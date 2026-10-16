"""Bounded frozen-app smoke check with startup diagnostics on every OS."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import desktop_platform as desktop


def main():
    executable = Path(sys.argv[1]).resolve()
    report = ROOT / "dev/frozen-smoke.json"
    command = [str(executable), "--smoke-test", str(report), "--ui"]
    if sys.platform.startswith("linux"):
        command = ["xvfb-run", "-a", *command]
    try:
        subprocess.run(command, check=True, timeout=100)
        import json
        result = json.loads(report.read_text(encoding="utf-8"))
        assert result["passed"] and result["ui_bridge"]
    except BaseException:
        log = desktop.user_data_dir() / "crash.log"
        if log.is_file():
            print(log.read_text(encoding="utf-8"), flush=True)
        raise


if __name__ == "__main__":
    main()
