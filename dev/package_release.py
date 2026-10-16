"""Package only build artifacts, preserving Unix modes and macOS bundle symlinks."""
import os
import sys
import tarfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def package(folder, destination, system="windows"):
    folder, destination = Path(folder).resolve(), Path(destination).resolve()
    if system != "windows":
        return package_unix(folder, destination, system)
    binary = folder / "Syllark.exe"
    runtime = folder / "runtime"
    if not binary.is_file() or not (runtime / "ui.html").is_file():
        raise ValueError("Expected Syllark.exe and runtime/ui.html")
    # Only these two app artifacts: never settings, sources, backups or user files.
    files = [binary] + sorted(p for p in runtime.rglob("*") if p.is_file())
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".new")
    try:
        with ZipFile(temporary, "w", ZIP_DEFLATED, compresslevel=6) as archive:
            for path in files:
                archive.write(path, "Syllark/" + path.relative_to(folder).as_posix())
        with ZipFile(temporary) as archive:
            names = archive.namelist()
            assert len(names) == len(files)
            assert "Syllark/runtime/ui.html" in names
            assert "Syllark/runtime/locales/it.json" in names
            assert archive.testzip() is None, "Corrupt ZIP entry"
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(f"OK: {len(files)} files, {destination.stat().st_size / 1048576:.1f} MB, ZIP integrity verified")


def package_unix(folder, destination, system):
    if system not in ("linux", "macos"):
        raise ValueError("Unknown package system")
    binary = folder / ("Contents/MacOS/Syllark" if system == "macos" else "Syllark")
    runtime = folder / ("Contents/Resources" if system == "macos" else "runtime")
    if not binary.is_file() or not (runtime / "ui.html").is_file():
        raise ValueError("Expected the executable and bundled ui.html")
    roots = [folder] if system == "macos" else [binary, runtime]
    for root in roots:
        for path in [root, *root.rglob("*")]:
            if path.is_symlink() and not path.resolve().is_relative_to(folder):
                raise ValueError("Bundle symlink escapes the app: " + str(path))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".new")
    try:
        with tarfile.open(temporary, "w:gz", dereference=False) as archive:
            for root in roots:
                archive.add(root, arcname=folder.name + ("/" + root.relative_to(folder).as_posix() if root != folder else ""))
        with tarfile.open(temporary, "r:gz") as archive:
            entries = archive.getmembers()
            expected = folder.name + "/" + binary.relative_to(folder).as_posix()
            assert archive.getmember(expected).mode & 0o111, "Executable bit is missing"
            for entry in entries:
                if entry.isfile():
                    with archive.extractfile(entry) as stream:
                        while stream.read(1 << 20):
                            pass
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(f"OK: {len(entries)} entries, Unix permissions and links preserved: {destination}")


if __name__ == "__main__":
    package(*sys.argv[1:])
