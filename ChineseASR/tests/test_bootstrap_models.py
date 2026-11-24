import hashlib
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

import pytest


@pytest.fixture
def setup(tmp_path, monkeypatch):
    path=Path(__file__).resolve().parents[1]/'scripts/bootstrap_models.py'
    spec=importlib.util.spec_from_file_location('bootstrap_runtime_test',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT=tmp_path
    body=b'real-download-and-checksum-test'*100
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            start=int(self.headers.get('Range','bytes=0-').split('=')[1].split('-')[0])
            calls.append(start)
            self.send_response(206 if start else 200)
            self.send_header('Content-Length',str(len(body)-start))
            if start: self.send_header('Content-Range',f'bytes {start}-{len(body)-1}/{len(body)}')
            self.end_headers()
            self.wfile.write(body[start:])
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    asset={'asset_name':'model.bin','size':len(body),'sha256':hashlib.sha256(body).hexdigest(),'paths':['models/model.bin','aliases/model.bin']}
    manifest={'release_download_base':f'http://127.0.0.1:{server.server_port}','assets':[asset]}
    (tmp_path/'model-assets.json').write_text(json.dumps(manifest),encoding='utf-8')
    monkeypatch.setattr('sys.argv',['bootstrap_models.py'])
    yield module,tmp_path,body,calls,manifest
    server.shutdown()
    server.server_close()


def test_download_restores_main_and_alias_with_hash(setup):
    module,root,body,calls,_=setup
    module.main()
    assert (root/'models/model.bin').read_bytes()==body
    assert (root/'aliases/model.bin').read_bytes()==body
    assert calls==[0]


def test_resume_uses_range_and_completes(setup):
    module,root,body,calls,_=setup
    (root/'models').mkdir()
    (root/'models/model.bin.partial').write_bytes(body[:17])
    module.main()
    assert (root/'models/model.bin').read_bytes()==body
    assert calls==[17]


def test_verified_model_skips_network_on_second_launch(setup):
    module,_,_,calls,_=setup
    module.main()
    module.main()
    assert calls==[0]


def test_verify_only_missing_never_downloads(setup,monkeypatch):
    module,_,_,calls,_=setup
    monkeypatch.setattr('sys.argv',['bootstrap_models.py','--verify-only'])
    with pytest.raises(FileNotFoundError): module.main()
    assert not calls


def test_destination_cannot_escape_repository(setup):
    module,root,_,_,manifest=setup
    manifest['assets'][0]['paths']=['../outside.bin']
    (root/'model-assets.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='escapes'): module.main()
    assert not (root.parent/'outside.bin').exists()


def test_wrong_checksum_is_not_accepted(setup):
    module,root,_,calls,manifest=setup
    manifest['assets'][0]['sha256']='0'*64
    (root/'model-assets.json').write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError): module.main()
    assert len(calls)==4
    assert not (root/'models/model.bin').exists()
