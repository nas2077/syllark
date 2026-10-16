# Contributing

Syllark is a Windows, macOS and Linux desktop application. Development uses
Python 3.12, pywebview, and plain HTML, CSS, and JavaScript. See
[platform setup](docs/PLATFORMS.md) for native renderers and Linux libraries.

## Setup

```powershell
powershell -ExecutionPolicy Bypass -File dev\setup.ps1 -Quiet
dev\run.bat
```

On macOS/Linux run `python3.12 dev/setup.py`, then
`dev/.venv/bin/python src/app.py`. Use `dev/.venv/Scripts/python.exe` on Windows
and `dev/.venv/bin/python` on Unix. Keep application dependencies in
`dev/requirements.txt`; tested versions are recorded in `dev/constraints.txt`.

## Changes

Keep changes focused. Explain the problem, the resulting behavior, and how it
was checked. Comments should explain constraints or non-obvious decisions.
Code, filenames, comments, and project documentation use English. Translation
catalog values and multilingual test fixtures retain their own languages.

The Nas palette, spacing, tactile controls, and pixel artwork are shared design
rules. Use semantic CSS tokens instead of adding unrelated colors or effects.

Interface strings belong in every catalog under `src/locales`, with matching
keys and placeholders. The interface language is independent of the spoken
language. README content lives in `docs/readme-texts.json`; regenerate it with
`python dev/build_docs.py`.

## Checks

```powershell
dev\.venv\Scripts\python.exe dev\core_check.py
dev\.venv\Scripts\python.exe dev\access_check.py
dev\.venv\Scripts\python.exe dev\readability_check.py
dev\.venv\Scripts\python.exe dev\natural_contract_check.py
dev\.venv\Scripts\python.exe dev\model_matrix_check.py
dev\.venv\Scripts\python.exe dev\repository_check.py
```

These checks use temporary outputs and simulated media or engines. Native engine/audio and GUI bridge smoke checks run on all three systems.
The older interactive checks require a Windows desktop session: `ui_check.py`, `controls_check.py`,
`localization_check.py`, `design_check.py`, `navigation_check.py`, and
`access_ui_check.py`. Report live TikTok/model tests separately from offline
regressions. See [validation](docs/VALIDATION.md).

Run `dev/platform_check.py` for OS boundaries and `src/desktop_smoke.py report.json --ui`
for native engine loading, audio decoding and a real desktop bridge (no model download).
CI builds five native packages and tests the Linux x64 archive on Ubuntu, Debian
and Fedora. Build artifacts include a platform-specific dependency/license inventory.

## Public access

Syllark works with public content. Do not add account login, imported cookies,
browser-session reads, or authentication setup controls. Profile embeds are
discovery inputs, not complete account feeds. Preserve pagination, photo-post
audio, canonical links, and clear errors for unavailable content.

## Builds

Changing source does not update an executable. Build and verify each native
package before attaching it to a release. Do not commit environments, model
weights, generated runtime files, downloaded media, or release binaries.
See [release preparation](docs/RELEASING.md).
