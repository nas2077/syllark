# PyInstaller folder build. Run through dev/build.ps1.
# Shared runtime libraries remain separate; optional CUDA libraries download on demand.
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

ROOT = os.path.dirname(SPECPATH)
SRC = os.path.join(ROOT, "src")

datas = [
    (os.path.join(ROOT, "LICENSE"), "licenses"),
    (os.path.join(ROOT, "THIRD_PARTY_NOTICES.md"), "licenses"),
    (os.path.join(SRC, "i18n.js"), "."),
    (os.path.join(SRC, "controls.js"), "."),
    (os.path.join(SRC, "locales"), "locales"),
    (os.path.join(SPECPATH, "build", "licenses"), "licenses"),
    (os.path.join(SRC, "ui.html"), "."),
    (os.path.join(SRC, "icon.ico"), "."),
    (os.path.join(ROOT, ".github", "assets", "syllark.png"), "."),
    (os.path.join(SRC, "vendor", "orbi.js"), "vendor"),
    (os.path.join(SRC, "vendor", "orbi-icons.js"), "vendor"),
    (os.path.join(SRC, "vendor", "nas.css"), "vendor"),
    (os.path.join(SRC, "vendor", "nas.js"), "vendor"),
]
binaries = []
hiddenimports = collect_submodules("yt_dlp.extractor") + ["desktop_smoke", "runtime_check"]

# Include package data, native backends, and provider entry-point metadata.
packages = ["faster_whisper", "ctranslate2", "onnxruntime", "tokenizers", "av",
                "webview", "curl_cffi", "yt_dlp", "yt_dlp_ejs",
                "huggingface_hub", "certifi", "transcribe_cpp", "transcribe_cpp_native"]
if sys.platform == "win32":
    packages += ["clr_loader", "pythonnet"]
elif sys.platform.startswith("linux"):
    # Follow the renderer imports; collecting all QtPy modules pulls in unused Qt suites.
    hiddenimports += ["webview.platforms.qt", "PySide6.QtWebEngineCore",
                      "PySide6.QtWebEngineWidgets", "PySide6.QtWebChannel"]
else:
    hiddenimports += ["webview.platforms.cocoa"]
for package in packages:
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

# The native provider is discovered through its Python package entry point.
for package in ("transcribe-cpp", "transcribe-cpp-native"):
    datas += copy_metadata(package)

a = Analysis(
    [os.path.join(SRC, "app.py")],
    pathex=[SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["nvidia", "tkinter", "matplotlib", "torch", "tensorflow", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Syllark",
    icon=(os.path.join(SRC, "icon.ico") if sys.platform == "win32" else
          os.path.join(SPECPATH, "build", "Syllark.icns") if sys.platform == "darwin" else None),
    console=False,              # a window, no black console behind it
    contents_directory="runtime",
    version=os.path.join(SPECPATH, "version_info.txt") if sys.platform == "win32" else None,
    upx=False,                  # compressed dlls trip antiviruses and start slower
)

coll = COLLECT(exe, a.binaries, a.datas, name="Syllark", upx=False)
if sys.platform == "darwin":
    app = BUNDLE(coll, name="Syllark.app", icon=os.path.join(SPECPATH, "build", "Syllark.icns"),
                 bundle_identifier="io.github.nas2077.syllark",
                 info_plist={"CFBundleShortVersionString": "0.1.0", "NSHighResolutionCapable": True,
                             "LSMinimumSystemVersion": "15.0"})
