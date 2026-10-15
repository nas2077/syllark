# Transcription models

All four choices are integrated. No external model manager, local server,
account, or transcription API key is required. Weights download automatically
when a usable job starts and remain in the local cache.

| Choice | Engine | Approximate download | Use |
|---|---|---:|---|
| Natural | Qwen3-ASR 1.7B Q8_0 | 2.3 GB including language detection | Sentences and punctuation; default for new settings |
| Balanced | Whisper large-v3-turbo | 1.6 GB | General accuracy/speed balance |
| Thorough | Whisper large-v3 | 3.1 GB | Difficult audio; more time and memory |
| Lightweight | Whisper small | 0.5 GB | Smaller download and lower memory use |

Saved model choices are respected. To replace previous transcripts, disable
**Skip already transcribed** or redo individual items in the Gallery.

## Natural

[Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR) runs through
[transcribe.cpp](https://github.com/handy-computer/transcribe.cpp) with its bundled
CPU/Vulkan backend. A GPU backend failure retries on CPU once. No CUDA library
installation is needed for this engine.

[Silero VAD](https://github.com/snakers4/silero-vad) filters silence and short
transients. SpeechBrain VoxLingua107 helps detect sustained language changes.
Audio blocks preserve context around detected speech and split at substantial
pauses, language boundaries, or quiet positions within a 90-second limit.

Natural supports 30 recognition languages, including all 14 offered by the app.
The 107-language detector does not expand Qwen's recognition coverage. Whisper
remains available for its wider language support. Auto works independently for
each video and can report more than one language.

**Natural timestamps identify audio block starts, not individual word alignment.**
The engine does not provide a word-accuracy probability. Silence has no invented
language or confidence score.

Pinned Qwen model revision:
`3555bd238a8572bbace3ebf60d23b036dc0a5dbe` from
`handy-computer/Qwen3-ASR-1.7B-gguf`.
Pinned language detector revision:
`41cf26039e317c6b8883bf0a61b0785dc663fc26` from
`handy-computer/lang-id-voxlingua107-ecapa-gguf`.
Both model files use Apache-2.0 terms. See `src/licenses` and the dependency notices.

## Whisper

The three Whisper choices use faster-whisper/CTranslate2. NVIDIA acceleration
uses CUDA; missing supported GPU libraries can be downloaded when needed. CPU
fallback remains available. Model snapshots and required files are pinned and
checked before inference.

Recognition errors remain possible, particularly with names, weak speech,
overlapping voices, or rapid changes inside a short sentence. The text formatter
preserves recognized words rather than asking another model to rewrite them.
See [validation](VALIDATION.md) for measured coverage and limits.
