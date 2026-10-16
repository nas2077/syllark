"""Build a native desktop package on its target OS. Never cross-compile."""
import argparse
import hashlib
import platform
import subprocess
import sys
from pathlib import Path

from package_release import package

DEV = Path(__file__).resolve().parent


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True, cwd=DEV.parent)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-setup", action="store_true")
    args = parser.parse_args()
    if not args.skip_setup:
        run(sys.executable, DEV / "setup.py")
    python = DEV / (".venv/Scripts/python.exe" if sys.platform == "win32" else ".venv/bin/python")
    if not python.is_file():
        raise SystemExit("Run python3.12 dev/setup.py first.")
    if sys.platform == "darwin":
        icons = DEV / "build/Syllark.iconset"
        icons.mkdir(parents=True, exist_ok=True)
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                suffix = "@2x" if scale == 2 else ""
                run("sips", "-z", size * scale, size * scale, DEV.parent / ".github/assets/syllark.png",
                    "--out", icons / f"icon_{size}x{size}{suffix}.png")
        run("iconutil", "-c", "icns", icons, "-o", DEV / "build/Syllark.icns")
    run(python, DEV / "collect_licenses.py")
    run(python, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
        "--distpath", DEV / "build/dist", "--workpath", DEV / "build/work", DEV / "build.spec")
    system = {"win32": "windows", "darwin": "macos", "linux": "linux"}[sys.platform]
    arch = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64", "arm64": "arm64"}[platform.machine().lower()]
    extension = ".zip" if system == "windows" else ".tar.gz"
    destination = DEV / "dist" / f"Syllark-0.1.0-{system}-{arch}{extension}"
    folder = DEV / "build/dist" / ("Syllark.app" if system == "macos" else "Syllark")
    package(folder, destination, system=system)
    with destination.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    destination.with_name(destination.name + ".sha256").write_text(f"{digest}  {destination.name}\n", encoding="ascii")


if __name__ == "__main__":
    main()
