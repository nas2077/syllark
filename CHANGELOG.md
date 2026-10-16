# Changelog

## Unreleased

- Native macOS (Apple Silicon/Intel) and Linux (x64/ARM64) builds alongside Windows 11 x64.
- OS-specific app storage, Documents folders, locale detection, file opening, native
  title bars on macOS/Linux, sleep inhibition and Unix single-instance locks.
- Metal capability reporting for Natural on macOS; Windows-only automatic CUDA
  downloads no longer run on Linux. Existing Windows settings keep their path.
- Native packaging with preserved Unix permissions/macOS symlinks and SHA-256 files.
- Cross-platform CI builds, frozen GUI/native/audio smoke tests and Linux distro checks.
- Platform-specific license inventories, without overwriting source constraints.

## 0.1.0 â€” 2026-10-15

First public Syllark release.

- Local Qwen and Whisper recognition behind four integrated model choices.
- Public TikTok video/profile processing, a selectable gallery, photo-post audio,
  resume, per-video exports, combined collections, and a metadata index.
- Markdown/plain text, optional timestamps, and readable paragraph boundaries.
- Nas interface with a distinct Syllark bird mark, 14 languages, light/dark themes,
  keyboard controls, and reduced motion.
- English source documentation, automated regression/security checks, dependency
  inventory, third-party license texts, and LGPL-only shared media libraries.

- Parsed TikTok host validation rejects misleading domains and off-site share
  redirects before making a public request.

Existing local settings keep their legacy storage location for compatibility.
See [validation](docs/VALIDATION.md) for measured coverage and known limitations.
