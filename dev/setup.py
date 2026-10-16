"""Prepare the same Python 3.12 environment on each supported desktop OS."""
import argparse
import platform
import subprocess
import sys
import venv
from pathlib import Path

DEV = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Use Python 3.12 to build the tested desktop environment.")
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine not in ("amd64", "x86_64"):
        raise SystemExit("Windows currently requires x64 Python (also usable under Windows 11 ARM emulation).")
    environment = DEV / ".venv"
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.exists():
        venv.create(environment, with_pip=True)
    subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                    "-r", str(DEV / "requirements.txt"), "-c", str(DEV / "constraints.txt"),
                    "-r", str(DEV / "requirements-dev.txt")], check=True)
    if sys.platform == "win32":
        subprocess.run([str(python), str(DEV / "prepare_media.py")], check=True)
        wheel = DEV / "media/av-18.1.0+lgpl.1-cp311-abi3-win_amd64.whl"
        subprocess.run([str(python), "-m", "pip", "install", "--no-deps", str(wheel)], check=True)
    print("Ready. Run", python, DEV.parent / "src/app.py")


if __name__ == "__main__":
    main()
