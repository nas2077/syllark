# Native desktop releases

The source contains no executable, venv, model weights or user media. Published
packages live in [Releases](https://github.com/nas2077/syllark/releases).
The existing v0.1.0 release is Windows-only. Cross-platform candidates are built
by Checks; they do not replace the published release.

## Packages and verification

| Target | Archive | Launch after extraction |
|---|---|---|
| Windows x64 | `Syllark-0.1.0-windows-x64.zip` | `Syllark/Syllark.exe` |
| Mac Apple Silicon | `Syllark-0.1.0-macos-arm64.tar.gz` | `Syllark.app` |
| Mac Intel | `Syllark-0.1.0-macos-x64.tar.gz` | `Syllark.app` |
| Linux x64 | `Syllark-0.1.0-linux-x64.tar.gz` | `Syllark/Syllark` |
| Linux ARM64 | `Syllark-0.1.0-linux-arm64.tar.gz` | `Syllark/Syllark` |

Candidates retain the app version until a new release is assigned. Identify them
by the Actions run/commit, not the old release tag. Each archive has a `.sha256`
file. Compare PowerShell `Get-FileHash <archive> -Algorithm SHA256`, Linux
`sha256sum -c <archive>.sha256` or macOS `shasum -a 256 -c <archive>.sha256`.
For the old Windows release use its `SHA256SUMS.txt` instead.

Keep the complete runtime beside Windows/Linux executables. Extract Unix
archives with `tar -xzf <archive>` to preserve permissions and symlinks. On macOS
move the complete `.app` into Applications. Windows builds are unsigned; Mac
builds are ad-hoc signed without Developer ID/notarization. Gatekeeper may block
candidates. Checksums verify integrity, not publisher identity. Do not disable
system security globally. Decide signing/notarization before public Mac releases.

## Build

Install Python 3.12 and [platform prerequisites](PLATFORMS.md), then run
`python3.12 dev/build.py` on macOS/Linux or `python dev/build.py` on Windows.
The original Windows `dev/build.ps1` entry point remains available.

The Python entry point creates/uses `dev/.venv`, installs constrained dependencies,
prepares verified LGPL media on Windows only, collects platform-specific license
texts and dependency inventory, and runs PyInstaller. Use `--skip-setup` for an
already prepared venv. Native folders/apps go to `dev/build/dist`; verified
archives and checksums go to `dev/dist`. Builds do not update installed copies,
tag commits or publish releases. Models download separately from pinned upstream
repositories.

Unix archives preserve executable modes and macOS symlinks. Only build artifacts
are packaged, excluding sibling user data. Actual licenses and inventory are
bundled under `licenses`; wheel licenses are under `python/<package>/distribution/`.
Collection does not rewrite source constraints or the historical Windows inventory
in docs. Review [Unix media licensing](MEDIA.md) separately from Windows LGPL media.

## CI and release validation

Checks builds five candidates on native OS/architecture runners, checks frozen
engines/audio and a real GUI bridge, then launches the Linux x64 archive on
Ubuntu 26.04, Debian 13 and Fedora 44. Passing build artifacts last 14 days and
require GitHub sign-in. Workflow repository permissions are read-only.

Before publication:

1. Assign the new version in metadata, archive names and changelog.
2. Require all build/distro jobs and [regressions](VALIDATION.md) to pass.
3. Exercise real speech/silence, CPU/GPU fallback, cancellation, folder dialogs,
   file opening, native controls and Unicode exports on each OS. Ordinary startup
   must not download models.
4. Review each exact archive's native licenses and source/build materials;
   preserve the Windows FFmpeg inputs documented in [MEDIA.md](MEDIA.md).
5. Decide signing/notarization, attach archives/checksums, tag the reviewed source,
   and record untested hardware/desktop combinations.
