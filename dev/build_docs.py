"""Render the English project README from its authored content."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    data = json.loads((ROOT / 'docs/readme-texts.json').read_text(encoding='utf-8'))
    text = '\n\n'.join(data['en']['sections']).rstrip() + '\n'
    (ROOT / 'README.md').write_bytes(text.encode('utf-8'))
    print('Rendered English README.')


if __name__ == '__main__':
    main()
