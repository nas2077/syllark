"""Repack the pinned PyAV wheel against a pinned LGPL-only FFmpeg build.

PyAV extension imports are changed to the standard shared-library names.
The original wheel and upstream FFmpeg archive are verified before use.
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import re
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / 'dev/media'
LOCK = json.loads((ROOT / 'dev/media.lock.json').read_text(encoding='utf-8'))


def fetch(info):
    path = CACHE / (info.get('wheel') or info['archive'])
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == info['sha256']:
        return path
    for url in [info['url'], info.get('mirror_url')]:
        if not url:
            continue
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Syllark-build'})
            with urllib.request.urlopen(request, timeout=90) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != info['sha256']:
                raise ValueError('SHA-256 mismatch: ' + url)
            path.write_bytes(data)
            return path
        except (urllib.error.URLError, TimeoutError):
            continue
    raise RuntimeError('Could not download verified build input: ' + path.name)


def unpack(archive, target):
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            path = (target / member.filename).resolve()
            if not path.is_relative_to(target.resolve()):
                raise ValueError('Archive path escapes extraction directory')
        bundle.extractall(target)


def repack():
    CACHE.mkdir(parents=True, exist_ok=True)
    output = CACHE / ('av-' + LOCK['repacked_version'] + '-cp311-abi3-win_amd64.whl')
    manifest = CACHE / 'media-provenance.json'
    if output.exists() and manifest.exists():
        saved = json.loads(manifest.read_text(encoding='utf-8'))
        if (saved.get('pyav') == LOCK['pyav'] and saved.get('ffmpeg') == LOCK['ffmpeg']
                and saved.get('wheel_sha256') == hashlib.sha256(output.read_bytes()).hexdigest()):
            print('Verified cached LGPL wheel:', output.name)
            return output
    wheel, media = fetch(LOCK['pyav']), fetch(LOCK['ffmpeg'])
    with tempfile.TemporaryDirectory(prefix='syllark-media-', dir=CACHE) as temporary:
        work = Path(temporary)
        package = work / 'wheel'
        package.mkdir()
        unpack(wheel, package)
        ffmpeg = work / 'ffmpeg'
        ffmpeg.mkdir()
        unpack(media, ffmpeg)
        source_bin = next(ffmpeg.glob('*/bin'))
        libraries = {p.name.lower(): p for p in source_bin.glob('*.dll')}
        if len(libraries) != 7 or any('x264' in n or 'x265' in n for n in libraries):
            raise ValueError('Unexpected LGPL archive library set')
        exports = {}
        for name, path in libraries.items():
            image = pefile.PE(str(path))
            exports[name] = {s.name for s in image.DIRECTORY_ENTRY_EXPORT.symbols}
        changed = 0
        for extension in (package / 'av').rglob('*.pyd'):
            data = bytearray(extension.read_bytes())
            image = pefile.PE(data=data)
            touched = False
            for entry in image.DIRECTORY_ENTRY_IMPORT:
                old = entry.dll.decode('ascii')
                new = re.sub(r'-[a-f0-9]{32}(?=\.dll$)', '', old)
                if new == old:
                    continue
                if new.lower() not in libraries:
                    raise ValueError('Unexpected extension library: ' + old)
                missing = {i.name for i in entry.imports if i.name} - exports[new.lower()]
                if missing:
                    raise ValueError('FFmpeg ABI mismatch: ' + repr(missing))
                offset = image.get_offset_from_rva(entry.struct.Name)
                replacement = new.encode('ascii') + b'\0'
                data[offset:offset+len(old)+1] = replacement.ljust(len(old)+1, b'\0')
                touched = True
            if touched:
                extension.write_bytes(data)
                changed += 1
        old_libs = (package / 'av.libs').resolve()
        if not old_libs.is_relative_to(work.resolve()) or old_libs.name != 'av.libs':
            raise ValueError('Unsafe library replacement path')
        shutil.rmtree(old_libs)
        old_libs.mkdir()
        for path in libraries.values():
            shutil.copy2(path, old_libs / path.name)
        metadata = next(package.glob('av-*.dist-info'))
        renamed = package / ('av-' + LOCK['repacked_version'] + '.dist-info')
        metadata.rename(renamed)
        meta_path = renamed / 'METADATA'
        text = meta_path.read_text(encoding='utf-8').replace('Version: 18.1.0', 'Version: '+LOCK['repacked_version'])
        meta_path.write_bytes(text.encode('utf-8'))
        license_path = next(ffmpeg.glob('*/LICENSE.txt'))
        license_folder = renamed / 'licenses'
        license_folder.mkdir(exist_ok=True)
        shutil.copy2(license_path, license_folder / 'FFmpeg-LGPL-3.0.txt')
        notice = {'pyav': LOCK['pyav'], 'ffmpeg': LOCK['ffmpeg'],
                  'modification': 'Extension DLL import names repointed to LGPL shared FFmpeg libraries.',
                  'modified_extensions': changed, 'libraries': sorted(libraries),
                  'repacked_version': LOCK['repacked_version']}
        (license_folder / 'SYLLARK-MEDIA.json').write_bytes((json.dumps(notice, indent=2)+'\n').encode())
        rows = []
        record = renamed / 'RECORD'
        for path in sorted(package.rglob('*')):
            if path.is_file() and path != record:
                data = path.read_bytes()
                digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
                rows.append([path.relative_to(package).as_posix(), 'sha256='+digest, str(len(data))])
        rows.append([record.relative_to(package).as_posix(), '', ''])
        buffer = io.StringIO(newline='')
        csv.writer(buffer, lineterminator='\n').writerows(rows)
        record.write_bytes(buffer.getvalue().encode())
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            for path in sorted(package.rglob('*')):
                if path.is_file():
                    bundle.write(path, path.relative_to(package).as_posix())
        notice['wheel_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
        (CACHE / 'media-provenance.json').write_bytes((json.dumps(notice, indent=2)+'\n').encode())
        print('Verified imports in', changed, 'extensions; LGPL wheel:', output.name)
    return output


if __name__ == '__main__':
    repack()
