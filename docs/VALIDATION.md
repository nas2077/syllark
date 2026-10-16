# Validation

Recorded on Windows 11 x64 with WebView2, Python 3.12, and an RTX 4060.
Results describe observed coverage; they do not guarantee transcription accuracy.

## Automated regressions

Run from the repository root after `dev/setup.ps1`:

```powershell
dev\.venv\Scripts\python.exe dev\repository_check.py
dev\.venv\Scripts\python.exe dev\core_check.py
dev\.venv\Scripts\python.exe dev\access_check.py
dev\.venv\Scripts\python.exe dev\readability_check.py
dev\.venv\Scripts\python.exe dev\natural_contract_check.py
dev\.venv\Scripts\python.exe dev\model_matrix_check.py
```

The release preparation passed 55 core, 24 anonymous-access, 72 readability,
and 10 native-contract checks. The matrix covered 10,080 export roundtrips,
4,320 pipelines with **mocked recognition/media**, and 41 engine/cache contracts.
These checks exercise application behavior, not speech-recognition quality.
GitHub Actions repeats this offline group and audits the pinned Python packages.

Interactive WebView2 checks passed 77 UI assertions, four models across all 14
locales and both themes, 144 focus checks, 240 navigation switches, localization,
anonymous-access controls, motion preferences, and command handling. These
require an interactive Windows desktop and run locally rather than on CI.

## Real audio and public network coverage

The recognition integration was exercised on 266 cases: 12 public creator clips
in automatic/manual Italian modes, 112 distinct FLEURS recordings in automatic
and manual modes across 14 languages, bilingual pairs, noisy recordings, and
noise/tone negatives. Additional checks covered digital silence, cancellation,
engine reuse, concurrent requests, and 96 creator export variants.

Anonymous network checks sampled 20 accessible public profiles and produced 39
transcripts. A separate complete NASA feed returned 56 posts: all 56 processed,
then all 56 skipped on resume without duplicates. Five unavailable discovery
attempts were recorded separately. A feed can change; these are observations
from the test date, not permanent account totals.

These broader integration runs preceded the Syllark identity and media-packaging
changes. The recognition logic was retained. Release preparation repeated the
interactive regressions and tested the new executable with real offline CPU and
Vulkan inference on two speech recordings and a no-speech ASMR recording, with
four exports per case. The rebuilt media libraries decoded 124 retained WAVs to
bit-identical samples. The final binary check compares compiled application
modules, UI, vendor kit, catalogs, and license files against source, then opens
the executable with disposable settings and an empty model cache.

Creator listening samples came from public `@alexciriaco_` (12 clips, 589.49
seconds). They are not a complete account export or a human-verified gold corpus.
FLEURS samples are small diagnostics, not the official full benchmark. WER
normalization ignores punctuation; Chinese/Japanese diagnostics use CER.
Downloaded audio, transcripts, personal paths, model weights, and raw local
reports are excluded from the source repository.

## Security and limits

CodeQL and dependency auditing have separate workflow badges. The first CodeQL
run identified URL substring validation; it was replaced with parsed-host and
scheme validation, with regressions for spoofed domains, userinfo, unsafe ports,
and off-site redirects. The local Python
audit found no known vulnerabilities in the pinned dependency set at preparation
time. This does not audit every native DLL or prove absence of vulnerabilities.
Checksums verify package integrity; this release has no Windows code-signing
certificate and no third-party certification.

Not verified: a completely clean Windows installation, every GPU/driver,
spontaneous rapid code switching, overlapping speakers, or word alignment.
Natural timestamps identify audio-block starts. There is no ElevenLabs parity
claim, human-verified accuracy percentage, or promise of error-free recognition.

See [model limitations](MODELS.md), [media packaging](MEDIA.md), and
[release checks](RELEASING.md).

## Cross-platform change

The Checks workflow now builds Windows x64, macOS arm64/x64 and Linux x64/arm64.
It runs offline regressions and OS-boundary tests, then loads both native engines,
ONNX Runtime and PyAV from the frozen app, decodes generated silent WAV audio,
and crosses the real JavaScript/Python bridge in a desktop WebView. The same
Linux x64 archive is launched in Ubuntu 26.04, Debian 13 and Fedora 44 containers
under Xvfb. Containers disable Chromium sandboxing only because they run as root.
Normal application startup keeps the normal renderer sandbox settings.

These are build/runtime smoke checks, not real-speech accuracy, GPU performance,
Wayland interaction, macOS notarization or Windows 11 hardware certification.
Candidate artifacts are available only for successful builds. Validate real model
inference, file dialogs, exports, cancellation and native window controls on each
OS before publishing a release. Historical Windows results above apply to 0.1.0.
