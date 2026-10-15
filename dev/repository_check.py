"""Validate the public source manifest, locale contracts, and documentation links."""
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent


def check():
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    files = [ROOT / name for name in names if name]
    assert files, 'No tracked source files'
    forbidden = {'.exe', '.dll', '.pyd', '.gguf', '.bin', '.whl', '.zip', '.wav', '.mp4', '.pyc'}
    for file in files:
        assert file.is_file(), f'Missing tracked file: {file.relative_to(ROOT)}'
        assert file.suffix.lower() not in forbidden, f'Generated binary in source: {file.name}'
        assert file.stat().st_size < 5 * 1024 * 1024, f'Unexpected large file: {file.name}'
        assert not any(p in {'.venv', 'runtime', 'backups', 'publication', '__pycache__'}
                       for p in file.relative_to(ROOT).parts)
        if file.suffix.lower() not in {'.py', '.js', '.css', '.html', '.md', '.json', '.yml', '.ps1', '.bat'}:
            continue
        text = file.read_text(encoding='utf-8-sig')
        assert not re.search(r'(?i)[a-z]:[/\\]Users[/\\](?!(?:Public|you|someone)\b)', text), f'Personal path: {file.name}'
        assert not re.search(r'gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}', text), f'Credential: {file.name}'
        assert ('-----BEGIN ' + 'PRIVATE KEY-----') not in text, f'Private key: {file.name}'
        if file.suffix == '.md' and not file.is_relative_to(ROOT / 'src/licenses'):
            for match in re.finditer(r'!?\[[^\]]*\]\(([^)]+)\)', text):
                link = match[1].strip().strip('<>')
                if urlsplit(link).scheme or link.startswith('#'):
                    continue
                target = (file.parent / unquote(link.split('#')[0])).resolve()
                assert target.is_relative_to(ROOT), f'Link escapes repository: {link}'
                assert target.exists(), f'Broken link in {file.name}: {link}'

    locale_dir = ROOT / 'src/locales'
    languages = json.loads((locale_dir / 'languages.json').read_text(encoding='utf-8'))
    catalogs = {item['code']: json.loads((locale_dir / (item['code'] + '.json')).read_text(encoding='utf-8'))
                for item in languages}
    assert len(catalogs) == 14
    base = catalogs['en']
    for language, catalog in catalogs.items():
        assert catalog.keys() == base.keys(), f'Locale keys: {language}'
        for key, value in catalog.items():
            assert isinstance(value, str)
            assert sorted(re.findall(r'\{\w+\}', value)) == sorted(re.findall(r'\{\w+\}', base[key])), (language, key)

    authored = json.loads((ROOT / 'docs/readme-texts.json').read_text(encoding='utf-8'))
    assert set(authored) == {'en'}
    expected = '\n\n'.join(authored['en']['sections']).rstrip() + '\n'
    assert (ROOT / 'README.md').read_text(encoding='utf-8') == expected, 'Run dev/build_docs.py'
    print(f'PASS: {len(files)} public files, English README source, 14 matching locale catalogs and documentation links.')


if __name__ == '__main__':
    check()
