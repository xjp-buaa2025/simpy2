"""Transport boundaries and expired-image behavior; no scheduler or playback mutations."""
import asyncio
import json
import struct
import pytest
from fastapi import FastAPI, HTTPException
from app.api import vr_mirror as mirror


def jpeg(width=640, height=360):
    # Enough header to exercise relay metadata validation; Unity decode is tested separately with actual JPEGs.
    return b'\xff\xd8\xff\xc0' + struct.pack('>HBHHB', 8, 8, height, width, 1) + b'\xff\xd9'


def test_demand_expiry_stale_frames_and_no_queue():
    now = [10.0]
    relay = mirror.Relay(lambda: now[0])
    assert not relay.state()['demand']
    relay.status('vr', 'xr_left_eye', 'active')
    with pytest.raises(HTTPException):
        relay.publish('vr', 0, jpeg())
    relay.viewer('pc', True)
    assert relay.publish('vr', 0, jpeg())['live']
    response = relay.read(-1)
    assert response.status_code == 200 and response.body == jpeg()
    assert relay.read(0, 'vr').status_code == 304
    now[0] += .2
    relay.publish('vr', 1, jpeg(480, 480))
    assert relay.sequence == 1 and relay.width == 480  # Only the latest frame is retained.
    now[0] += 2.1
    assert relay.read(-1).status_code == 204
    assert not relay.state()['live']
    now[0] += 1
    assert not relay.state()['demand']


def test_multiple_headsets_sequence_rate_and_reconnection():
    now = [10.0]
    relay = mirror.Relay(lambda: now[0])
    relay.viewer('pc', True)
    relay.status('vr1', 'xr_left_eye', '')
    relay.publish('vr1', 10, jpeg())
    with pytest.raises(HTTPException) as conflict:
        relay.status('vr2', 'xr_left_eye', '')
    assert conflict.value.status_code == 409
    with pytest.raises(HTTPException):
        relay.publish('vr1', 9, jpeg())
    with pytest.raises(HTTPException) as rate:
        relay.publish('vr1', 11, jpeg())
    assert rate.value.status_code == 429
    now[0] += 3.1
    relay.viewer('pc', True)
    relay.status('vr2', 'editor_test', '')
    relay.publish('vr2', 0, jpeg())
    # A new publisher starting at an old sequence still returns the new image.
    assert relay.read(0, 'vr1').status_code == 200
    relay.status('vr2', 'unavailable', 'tracking lost')
    assert relay.read(-1).status_code == 204


def test_twenty_fps_and_burst_limit_preserve_latest_frame():
    now = [10.0]
    relay = mirror.Relay(lambda: now[0])
    relay.viewer('pc', True)
    relay.status('vr', 'xr_left_eye', '')
    assert relay.state()['target_fps'] == 20
    for sequence in range(20):
        now[0] = 10 + sequence / 20
        assert relay.publish('vr', sequence, jpeg())['sequence'] == sequence
    with pytest.raises(HTTPException) as rate:
        relay.publish('vr', 20, jpeg(480, 480))
    assert rate.value.status_code == 429 and rate.value.headers['Retry-After'] == '0.05'
    assert relay.sequence == 19 and relay.width == 640
    now[0] += .04
    assert relay.publish('vr', 21, jpeg(480, 480))['width'] == 480


def test_rolling_window_hard_limit_and_transport_jitter():
    now=[10.0];relay=mirror.Relay(lambda:now[0]);relay.viewer('pc',True);relay.status('vr','editor_test','')
    # Brief 32ms gaps may occur in a 20 FPS stream and must not be misclassified.
    for seq,delta in enumerate([0,.032,.068,.032,.068]):
        now[0]+=delta;relay.publish('vr',seq,jpeg())
    now[0]=12.;relay.viewer('pc',True)
    for seq in range(5,35):
        now[0]=12+(seq-5)*.018;relay.publish('vr',seq,jpeg())
    now[0]=12.55
    with pytest.raises(HTTPException) as rate:relay.publish('vr',35,jpeg())
    assert rate.value.status_code==429 and relay.sequence==34 and len(relay.frame_times)==30
    now[0]=13.02
    assert relay.publish('vr',36,jpeg())['sequence']==36


def request(method, path, body=b'', query=b'', headers=None):
    app = FastAPI()
    app.include_router(mirror.router, prefix='/mirror')
    async def run():
        messages = []
        async def receive(): return dict(type='http.request', body=body, more_body=False)
        async def send(message): messages.append(message)
        await app(dict(type='http', asgi={'version':'3.0'}, http_version='1.1', method=method, scheme='http', path=path,
                       raw_path=path.encode(), query_string=query, root_path='', headers=headers or [], client=('127.0.0.1',1), server=('localhost',80)),receive,send)
        status = next(m['status'] for m in messages if m['type']=='http.response.start')
        data=b''.join(m.get('body',b'') for m in messages)
        return status,data
    return asyncio.run(run())


def test_http_limits_and_read_contract(monkeypatch):
    monkeypatch.setattr(mirror, 'relay', mirror.Relay())
    def post(path, value):
        return request('POST', path, json.dumps(value).encode(), headers=[(b'content-type',b'application/json')])
    assert post('/mirror/viewer', {'viewer_id':'pc','active':True})[0] == 200
    assert post('/mirror/publisher', {'publisher_id':'vr','source':'editor_test'})[0] == 200
    assert post('/mirror/viewer', {'viewer_id':'../invalid','active':True})[0] == 400
    query=b'publisher_id=vr&sequence=0'
    assert request('POST','/mirror/frame',jpeg(),query,[(b'content-type',b'image/jpeg')])[0]==200
    assert request('GET','/mirror/frame.jpg')[0]==200
    assert request('POST','/mirror/frame',b'x'*(mirror.MAX_BYTES+1),query,[(b'content-type',b'image/jpeg')])[0]==413
    assert request('POST','/mirror/frame',jpeg(),query,[(b'content-type',b'text/plain')])[0]==415
    assert request('POST','/mirror/frame',jpeg(4000,4000),query,[(b'content-type',b'image/jpeg')])[0]==400
    assert request('POST','/mirror/frame',b'not a jpeg',query,[(b'content-type',b'image/jpeg')])[0]==400
    assert post('/mirror/publisher', {'publisher_id':'vr','source':'fake_source'})[0]==422
    assert post('/mirror/viewer', {'viewer_id':'pc','active':False})[0]==200
    assert not mirror.relay.state()['demand']
