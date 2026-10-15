# PyInstaller folder build. Run through dev/build.ps1.
# Shared runtime libraries remain separate; optional CUDA libraries download on demand.
import os

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

ROOT = os.path.dirname(SPECPATH)
SRC = os.path.join(ROOT, "src")

datas = [
    (os.path.join(ROOT, "LICENSE"), "licenses"),
    (os.path.join(ROOT, "THIRD_PARTY_NOTICES.md"), "licenses"),
    (os.path.join(SRC, "i18n.js"), "."),
    (os.path.join(SRC, "controls.js"), "."),
    (os.path.join(SRC, "locales"), "locales"),
    (os.path.join(SRC, "licenses"), "licenses"),
    (os.path.join(SRC, "ui.html"), "."),
    (os.path.join(SRC, "icon.ico"), "."),
    (os.path.join(SRC, "vendor", "orbi.js"), "vendor"),
    (os.path.join(SRC, "vendor", "orbi-icons.js"), "vendor"),
    (os.path.join(SRC, "vendor", "nas.css"), "vendor"),
    (os.path.join(SRC, "vendor", "nas.js"), "vendor"),
]
binaries = []
hiddenimports = collect_submodules("yt_dlp.extractor")

# Include package data, native backends, and provider entry-point metadata.
for package in ("faster_whisper", "ctranslate2", "onnxruntime", "tokenizers", "av",
                "webview", "clr_loader", "pythonnet", "curl_cffi", "yt_dlp", "yt_dlp_ejs",
                "huggingface_hub", "certifi", "transcribe_cpp", "transcribe_cpp_native"):
    try:
        d, b, h = collect_all(package)
    except Exception:
        continue
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
    icon=os.path.join(SRC, "icon.ico"),
    console=False,              # a window, no black console behind it
    contents_directory="runtime",
    version=os.path.join(SPECPATH, "version_info.txt"),
    upx=False,                  # compressed dlls trip antiviruses and start slower
)

coll = COLLECT(exe, a.binaries, a.datas, name="Syllark", upx=False)
