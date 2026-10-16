# Desktop platforms

The build matrix covers current desktop families, with native binaries rather
than a build for every distro release.

| System | Build target | Desktop |
|---|---|---|
| Windows 11 | x64, built on Windows Server 2025 | Microsoft WebView2 |
| macOS 15+ | arm64 (Apple Silicon), x64 (Intel) | Cocoa / system WKWebView |
| Ubuntu 24.04+ | x64 and arm64 | Qt WebEngine / PySide6 |
| Debian 13, Fedora 44 | Same Linux x64 archive checked in containers | Qt WebEngine / PySide6 |

Ubuntu 26.04 also exercises the packaged app. Recent Mint 22+, Pop!_OS,
Arch/Manjaro and openSUSE Tumbleweed with glibc 2.39+ are compatibility targets,
not separately certified builds. Linux arm64 is tested on Ubuntu; other arm64
distro combinations need hardware validation. Alpine/musl, 32-bit PCs, mobile
and obsolete OS releases are outside the matrix. Windows 11 ARM users can try
x64 emulation; not all recognition dependencies offer native Windows ARM builds.

## Run from source

Install a native **Python 3.12** for your architecture. On Windows:

```powershell
python dev/setup.py
dev\.venv\Scripts\python.exe src\app.py
```

On macOS/Linux:

```sh
python3.12 dev/setup.py
dev/.venv/bin/python src/app.py
```

macOS uses the PyObjC dependencies selected by pywebview. Linux explicitly
installs QtPy and the LGPL PySide6 renderer. Linux needs a graphical desktop
(X11, or Wayland with XWayland), graphics drivers and system desktop libraries.

Ubuntu 24.04/26.04 and Debian 13:

```sh
sudo apt install python3-venv libegl1 libopengl0 libgl1 libnss3 libopus0 libminizip1 libpulse0 libasound2t64 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xinerama0 libxcb-randr0 libxcb-render-util0 libdbus-1-3 xdg-utils
```

Fedora:

```sh
sudo dnf install mesa-libEGL mesa-libGL libglvnd-opengl nss opus minizip pulseaudio-libs alsa-lib libxkbcommon-x11 xcb-util-cursor xcb-util-wm xcb-util-keysyms xcb-util-image xcb-util-renderutil dbus-libs xdg-utils
```

Install Python 3.12 separately if the distro default is newer. Native archive
users do not need Python. Linux packages are built on Ubuntu 24.04 (glibc 2.39);
older systems may reject them. Do not disable Chromium's sandbox for normal use.
See [pywebview renderer requirements](https://pywebview.flowrl.com/guide/installation.html).

## Engines and desktop integration

Natural uses transcribe.cpp's automatic backend: Metal on compatible Macs,
Vulkan where available on Windows/Linux, and CPU fallback. See the upstream
[native wheel matrix](https://pypi.org/project/transcribe-cpp-native/0.4.0/).
Mac Intel pins ONNX Runtime 1.23.2, the last available native Intel wheel; other
targets use 1.31.0. Track upstream Intel support before future dependency updates.
Whisper uses CTranslate2 CPU on every platform, with optional NVIDIA CUDA on
Windows/Linux. On Linux install compatible CUDA 12/cuDNN 9 and expose their shared
libraries to the loader **before starting Syllark**. Windows automatic CUDA
downloads never run on Unix. Whisper does not use Apple's Metal backend.

Windows preserves `%LOCALAPPDATA%/TikTok Transcriber`. macOS uses
`~/Library/Application Support/Syllark`. Linux uses `$XDG_DATA_HOME/syllark`
(default `~/.local/share/syllark`). Linux respects `XDG_DOCUMENTS_DIR`, macOS uses
`~/Documents`, and Windows follows redirected Documents. App folders can be
read-only. Model caches follow the Hugging Face cache configuration.

macOS/Linux use native title bars for resizing, snapping and accessibility.
Windows keeps its custom bar. Sleep inhibition is best-effort via the Windows
API, macOS `caffeinate` or Linux `systemd-inhibit`; permissions can deny it.
Unix advisory locks prevent a second process; a second launch exits without
raising the existing window. Windows continues to raise its existing window.

## Build and verification

Run `python3.12 dev/build.py` on macOS/Linux or `python dev/build.py` on Windows.
Build on the target OS and architecture; PyInstaller does not cross-compile.
See [release packaging](RELEASING.md). Automated checks cover native imports,
audio decoding and the real GUI bridge; real speech, GPU hardware, Wayland
interaction and signing/notarization still require release validation.
