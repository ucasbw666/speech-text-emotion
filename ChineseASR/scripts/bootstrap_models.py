"""Restore verified release model assets after downloading the GitHub source ZIP."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time

import requests

ROOT = Path(__file__).resolve().parents[2]


def sha256(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def safe_path(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('Model destination escapes repository root')
    return path


def fetch(asset, destination, base_url):
    temporary = destination.with_name(destination.name + '.partial')
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = base_url + '/' + asset['asset_name']
    for attempt in range(4):
        offset = temporary.stat().st_size if temporary.exists() else 0
        if offset > asset['size']:
            temporary.unlink()
            offset = 0
        try:
            print(f"Downloading {asset['asset_name']} ({asset['size']/1024**2:.1f} MiB)", flush=True)
            headers = {'Range': f'bytes={offset}-'} if offset else {}
            with requests.get(url, headers=headers, stream=True, timeout=(30, 120)) as response:
                response.raise_for_status()
                if offset and response.status_code != 206:
                    offset = 0
                if offset and not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
                    raise ValueError('Incorrect resumed download range')
                total = offset
                last = time.monotonic()
                with temporary.open('ab' if offset else 'wb') as target:
                    for block in response.iter_content(2 * 1024 * 1024):
                        if total + len(block) > asset['size']:
                            raise ValueError('Unexpected model response size')
                        target.write(block)
                        total += len(block)
                        if time.monotonic() - last > 5:
                            print(f"  {total / asset['size']:.0%}", flush=True)
                            last = time.monotonic()
            if temporary.stat().st_size != asset['size'] or sha256(temporary) != asset['sha256']:
                temporary.unlink(missing_ok=True)
                raise ValueError('Model SHA256 verification failed')
            temporary.replace(destination)
            return
        except (requests.RequestException, ValueError) as error:
            print(f'Download attempt {attempt+1} failed: {error}', flush=True)
            if attempt == 3:
                raise RuntimeError('Could not download model. Check network access and retry; partial downloads are resumed.') from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'model-assets.json').read_text(encoding='utf-8'))
    cache_file = ROOT / '.runtime' / 'verified-model-assets.json'
    cache = json.loads(cache_file.read_text(encoding='utf-8')) if cache_file.exists() else {}
    for asset in manifest['assets']:
        primary = safe_path(asset['paths'][0])
        stamp = cache.get(asset['sha256'], {})
        stat = primary.stat() if primary.is_file() else None
        cached = stat and stamp.get('size') == stat.st_size == asset['size'] and stamp.get('mtime_ns') == stat.st_mtime_ns
        correct = cached or (stat and stat.st_size == asset['size'] and sha256(primary) == asset['sha256'])
        if not correct:
            if args.verify_only:
                raise FileNotFoundError(f'Missing or invalid model: {primary}')
            fetch(asset, primary, manifest['release_download_base'])
        for relative in asset['paths'][1:]:
            alias = safe_path(relative)
            if not alias.is_file() or alias.stat().st_size != asset['size']:
                alias.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(primary, alias)
        stat = primary.stat()
        cache[asset['sha256']] = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
        print(f"Verified {asset['asset_name']}", flush=True)
    cache_file.parent.mkdir(exist_ok=True)
    cache_file.write_text(json.dumps(cache, indent=2), encoding='utf-8')
    print('All model assets are ready. No training dataset is required.', flush=True)


if __name__ == '__main__':
    main()
