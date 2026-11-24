"""Fetch pinned, checksum-identical models and publish them from a GitHub runner."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
SOURCES={
 'whisper-small-model.safetensors': 'https://huggingface.co/openai/whisper-small/resolve/973afd24965f72e36ca33b3055d56a652f456b4d/model.safetensors?download=true',
 'emotion2vec-plus-large-model.pt': 'https://huggingface.co/emotion2vec/emotion2vec_plus_large/resolve/6c303ba987b86b93193de93e34bb2b077a6bedc4/model.pt?download=true',
 'emotion-production-backbone-adapter.pth': 'https://media.githubusercontent.com/media/willinger566/voice-main/538403fb1940895f443904c303a0b448bbf6ab93/models/production/branch_1/backbone_adapter.pth',
}


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(8*1024**2),b''): value.update(block)
    return value.hexdigest()


def fetch(asset):
    name=asset['asset_name']
    path=ROOT/'.model-release'/name
    path.parent.mkdir(exist_ok=True)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(SOURCES[name],timeout=120) as response,path.open('wb') as target:
                total=0
                last=time.monotonic()
                while block:=response.read(4*1024**2):
                    target.write(block)
                    total+=len(block)
                    if time.monotonic()-last>=10:
                        print(f'Download {name}: {total/asset["size"]:.0%}',flush=True)
                        last=time.monotonic()
            if path.stat().st_size!=asset['size'] or digest(path)!=asset['sha256']:
                raise ValueError('Model checksum mismatch')
            print('SHA256 verified: '+name,flush=True)
            return path
        except Exception as error:
            print(f'Download attempt {attempt+1} for {name} failed: {type(error).__name__}',flush=True)
            if attempt==2: raise


def gh(*arguments,capture=False):
    return subprocess.run(['gh',*arguments],check=True,text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def main():
    if os.getenv('GITHUB_ACTIONS')!='true':
        raise RuntimeError('Run this release helper only in the GitHub workflow')
    manifest=json.loads((ROOT/'model-assets.json').read_text(encoding='utf-8'))
    repo=os.environ['GITHUB_REPOSITORY']
    tag=manifest['release_tag']
    with ThreadPoolExecutor(max_workers=3) as pool:
        paths=[future.result() for future in as_completed([pool.submit(fetch,a) for a in manifest['assets']])]
    releases=json.loads(gh('api',f'repos/{repo}/releases',capture=True))
    if not any(r['tag_name']==tag for r in releases):
        gh('release','create',tag,'--draft','--target','main','--title','Verified runtime models v1',
           '--notes','Runtime models with SHA256 checksums matching model-assets.json. Use the root launcher to restore them. Preserve original model and data license terms.')
    for path in paths:
        gh('release','upload',tag,str(path),'--clobber')
    releases=json.loads(gh('api',f'repos/{repo}/releases',capture=True))
    release=next(r for r in releases if r['tag_name']==tag)
    assets=json.loads(gh('api',f'repos/{repo}/releases/{release["id"]}/assets',capture=True))
    lookup={a['name']:a for a in assets}
    for expected in manifest['assets']:
        actual=lookup[expected['asset_name']]
        if actual['size']!=expected['size'] or actual.get('digest')!='sha256:'+expected['sha256']:
            raise ValueError('GitHub release digest mismatch: '+expected['asset_name'])
        print('Server-side SHA256 verified: '+expected['asset_name'],flush=True)
    gh('release','edit',tag,'--draft=false')
    print('Published verified runtime model release.',flush=True)


if __name__=='__main__': main()
