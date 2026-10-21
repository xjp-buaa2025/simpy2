"""Physical layout profile; legacy /layout endpoints remain unchanged."""
import time
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.factory_layout import LayoutError, load_json
from app.core.pt6a29_layout import PhysicalLayoutStore
from app.api.unity_playback import clock

router = APIRouter()
store = PhysicalLayoutStore()


class PublishRequest(BaseModel):
    client_id: str
    sim_id: str
    expected_revision: int
    layout: dict


class RestoreRequest(BaseModel):
    client_id: str
    sim_id: str
    expected_revision: int
    source: str = 'previous'


@router.get('/physical-layout.json')
def snapshot():
    try:
        return store.snapshot()
    except (OSError, ValueError) as e:
        raise HTTPException(503, '原场景29工位布局或当前回放尚未准备好') from e


@router.get('/physical-layout/default.json')
def default():
    return store.default


@router.post('/physical-layout/validate')
async def validate(request: Request):
    try:
        if request.headers.get('content-type', '').startswith('multipart/'):
            form = await request.form(); upload = form.get('file')
            if upload is None:
                raise HTTPException(400, '缺少布局文件')
            document = store.parse(upload.filename or '', await upload.read(2 * 1024 * 1024 + 1))
        else:
            body = await request.body()
            document = store.parse('layout.json', body)
        return store.validate(document)
    except LayoutError as e:
        return dict(valid=False, errors=e.errors, changes=[])


def publish(request, document):
    with clock._lock:
        state = clock.snapshot()
        if state['controller_id'] != request.client_id or not state['controller_connected']:
            raise HTTPException(409, '此PC没有播放控制权')
        if state['sim_id'] != request.sim_id:
            raise HTTPException(409, '排产已变化，请刷新预览')
        if state['playing']:
            raise HTTPException(409, '请先暂停仿真')
        try:
            return store.commit(document, request.expected_revision, request.sim_id)
        except RuntimeError as e:
            raise HTTPException(409, str(e)) from e
        except LayoutError as e:
            raise HTTPException(422, dict(errors=e.errors)) from e


@router.put('/physical-layout')
def apply(request: PublishRequest):
    return publish(request, request.layout)


@router.post('/physical-layout/restore')
def restore(request: RestoreRequest):
    if request.source not in {'default', 'previous'}:
        raise HTTPException(400, '恢复来源无效')
    try:
        document = store.default if request.source == 'default' else load_json(store.directory / 'previous.json')
    except OSError as e:
        raise HTTPException(404, '尚无上一版物理布局') from e
    return publish(request, document)


@router.get('/physical-layout/previous.json')
def previous():
    try:
        return load_json(store.directory / 'previous.json')
    except OSError as e:
        raise HTTPException(404, '尚无上一版物理布局') from e


@router.get('/physical-layout/export')
def export(format: str = Query('json', pattern='^(xlsx|json)$')):
    return Response(store.export(format),
                    media_type='application/json' if format == 'json' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f'attachment; filename="pt6a29_original_r{store.current["revision"]}.{format}"',
                             'Cache-Control': 'no-store'})


@router.post('/physical-layout/ack')
async def ack(request: Request):
    data = await request.json()
    if len(str(data.get('client_id', ''))) > 100 or len(str(data.get('status', ''))) > 200:
        raise HTTPException(400, '状态内容过长')
    now = time.monotonic()
    store.clients = {k: v for k, v in store.clients.items() if now - v['_seen'] < 20}
    store.clients[data.get('client_id', '')] = {**data, '_seen': now}
    return dict(revision=store.current['revision'], clients=[{k: v for k, v in c.items() if k != '_seen'} for c in store.clients.values()])
