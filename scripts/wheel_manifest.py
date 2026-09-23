"""Манифест всегда использует /, независимо от ОС, на которой его собрали."""
import hashlib
import json
from pathlib import Path


def build_manifest(root):
    root=Path(root)
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.glob('*/*.whl'))}


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]/'vendor/wheels'
    manifest=build_manifest(root)
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(f'{len(manifest)} wheel files checksummed')
