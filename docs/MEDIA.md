# Windows media libraries

The application reads audio through PyAV. Its Windows wheel includes FFmpeg
libraries with additional codec-license considerations. Syllark's public build
uses a pinned LGPL-only shared FFmpeg variant without x264/x265.

## Inputs and modification

`dev/media.lock.json` records the original PyAV 18.1.0 wheel and the FFmpeg
archive URLs and SHA-256 values. The upstream BtbN archive is mirrored as a
release asset because its daily archives have a limited retention period.

```powershell
dev\.venv\Scripts\python.exe dev\prepare_media.py
dev\.venv\Scripts\python.exe -m pip install --no-deps --force-reinstall dev\media\av-18.1.0+lgpl.1-cp311-abi3-win_amd64.whl
```

The script verifies both archives, checks every imported FFmpeg symbol, changes
40 extension import tables to the standard shared-library names, replaces the
bundled libraries, and rebuilds wheel metadata/RECORD. It changes no extension
instructions or application recognition logic. The wheel carries an explicit
local version and modification notice.

The DLLs remain separate in the application runtime. Replacement libraries must
provide the imported FFmpeg ABI; the repacking script checks symbol availability.
Build outputs and input archives stay under ignored `dev/media`.

## Sources and build materials

- [FFmpeg source at the distributed revision](https://github.com/FFmpeg/FFmpeg/tree/46d899d7a0).
- [BtbN build scripts and dependency source definitions](https://github.com/BtbN/FFmpeg-Builds/tree/63ac3265b0789ea16c7b1f8351cd2ad195a28722).
- [PyAV 18.1.0 source](https://github.com/PyAV-Org/PyAV/tree/v18.1.0).
- Syllark's import-table changes and packaging instructions: `dev/prepare_media.py`.

The BtbN tree contains the component source URLs, patches, configuration, and
container build steps. Its relevant target is `win64`, variant `lgpl-shared`,
release branch `8.1`; the FFmpeg commit is fixed by the lock file. The release also retains source snapshots for FFmpeg, PyAV, and the BtbN build
scripts; their revisions, original download URLs, and checksums are in
[media-sources.json](media-sources.json). Preserve these materials and source
access with a release. Read the full LGPL/GPL terms in
`src/licenses` rather than treating a metadata label as a certification.

## Verification

The resulting runtime reports LGPL version 3 or later and has no x264/x265 DLLs
or enabled GPL configuration. 124 retained WAV recordings decode to exactly the
same samples as the previous package. Frozen CPU/Vulkan inference and live
download/export checks are recorded separately in the release validation notes.

## macOS and Linux

The Windows DLL repacking step must never run on Unix. macOS/Linux builds use
platform-native PyAV 18.1.0 wheels and include their supplied license notices in
`licenses/python/av/distribution/`. These are different FFmpeg builds; the Windows
LGPL-only verification above is not a claim about Unix wheels. Inspect the exact
wheel notices, bundled codecs and source/build-material obligations before a
public release. Candidate builds include their own `licenses/dependencies.json`.
