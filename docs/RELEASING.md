# Windows releases

The source repository contains no executable, virtual environment, model weights,
downloaded user media, or build cache. Download runnable packages from
[GitHub Releases](https://github.com/nas2077/syllark/releases).

## Verify a download

Download `Syllark-0.1.0-windows-x64.zip` and `SHA256SUMS.txt` from the same release.
In PowerShell:

```powershell
Get-FileHash .\Syllark-0.1.0-windows-x64.zip -Algorithm SHA256
```

Compare the hash with the ZIP entry in the checksum file. Extract the entire
archive, then open `Syllark/Syllark.exe`. Keep `runtime` beside the executable.
The app requires Windows 10/11 x64 and Microsoft WebView2. The executable is
unsigned. Checksums provide integrity checking, not a publisher certificate.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File dev\build.ps1 -Quiet
```

The script creates/uses `dev/.venv`, installs constrained dependencies, verifies
the media inputs, installs the LGPL PyAV variant, collects license texts, and
builds with PyInstaller. Output goes to `dev/build/dist/Syllark`; the verified
ZIP goes to `dev/dist`. It does not overwrite an existing installed copy.

The initial public release was built and verified locally on Windows. Its
checksum is not a claim of reproducible byte-for-byte builds or GitHub build
attestation. GitHub's source checks and CodeQL run separately.

## Maintainer checklist

1. Update the version metadata, package name, and changelog together.
2. Pass the offline and interactive checks in [VALIDATION.md](VALIDATION.md).
3. Build with the pinned [media inputs](MEDIA.md), then run
   `dev/model_binary_check.py` against the exact release executable.
4. Exercise real speech, no speech, CPU, GPU fallback, and export paths in that
   executable. Check that ordinary startup does not download weights.
5. Inspect the ZIP contents, licenses, dependency inventory, and CRC verification.
6. Attach the ZIP, SHA-256 checksums, and pinned upstream FFmpeg input archive.
   Preserve corresponding source/build-material access documented in MEDIA.md.
7. Publish a tag matching the reviewed source commit. Record test scope and
   limitations; do not describe mocked cases as recognition benchmarks.

The initial source tag is `v0.1.0`. Model downloads remain at their pinned upstream
repositories and are not included in the application ZIP.
