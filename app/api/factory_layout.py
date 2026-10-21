"""Factory presentation layout endpoints, hosted beside the shared playback clock."""
import json
import time
from fastapi import APIRouter, File, HTTPException, UploadFile, Query
from fastapi.responses import Response
from pydantic import BaseModel
from app.core.factory_layout import LayoutStore, LayoutError, load_json
from app.api.unity_playback import clock

router=APIRouter()
store=LayoutStore()

class PublishRequest(BaseModel):
    client_id:str
    sim_id:str
    expected_revision:int
    layout:dict

class RestoreRequest(BaseModel):
    client_id:str
    sim_id:str
    expected_revision:int
    source:str='previous'

class AckRequest(BaseModel):
    client_id:str
    role:str
    revision:int
    sim_id:str
    status:str='applied'

@router.get('/layout.json')
def snapshot():
    try:return store.snapshot()
    except LayoutError as e:raise HTTPException(422,dict(errors=e.errors))
    except (OSError,ValueError) as e:raise HTTPException(503,'布局资源或当前回放尚未准备好') from e

@router.post('/layout/validate')
async def validate(file:UploadFile=File(...)):
    try:return store.validate(store.parse(file.filename or '',await file.read(2*1024*1024+1)))
    except LayoutError as e:return dict(valid=False,errors=e.errors,changes=[])

def publish(request,document):
    with clock._lock:
        state=clock.snapshot()
        if state['controller_id']!=request.client_id or not state['controller_connected']:raise HTTPException(409,'此 PC 没有播放控制权')
        if state['sim_id']!=request.sim_id:raise HTTPException(409,'排产已变化，请刷新预览')
        if state['playing']:raise HTTPException(409,'请先暂停仿真')
        try:return store.commit(document,request.expected_revision,request.sim_id)
        except RuntimeError as e:raise HTTPException(409,str(e))
        except LayoutError as e:raise HTTPException(422,dict(errors=e.errors))

@router.put('/layout')
def apply(request:PublishRequest):return publish(request,request.layout)

@router.post('/layout/restore')
def restore(request:RestoreRequest):
    if request.source not in ('default','previous'):raise HTTPException(400,'恢复来源无效')
    try:document=store.default if request.source=='default' else load_json(store.directory/'previous.json')
    except OSError:raise HTTPException(404,'尚无上一版布局')
    return publish(request,document)

@router.get('/layout/export')
def export(format:str=Query('xlsx',pattern='^(xlsx|json)$')):
    try:body=store.export(format)
    except OSError as e:raise HTTPException(503,'布局模板尚未安装') from e
    return Response(body,media_type='application/json' if format=='json' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="factory_layout_r{store.current["revision"]}.{format}"','Cache-Control':'no-store'})

@router.get('/layout/previous.json')
def previous():
    try:return load_json(store.directory/'previous.json')
    except OSError:raise HTTPException(404,'尚无上一版布局')

@router.post('/layout/ack')
def ack(request:AckRequest):
    if len(request.client_id)>100 or len(request.status)>200:raise HTTPException(400,'状态内容过长')
    now=time.monotonic()
    store.clients={key:value for key,value in store.clients.items() if now-value['_seen']<20}
    store.clients[request.client_id]=dict(**request.model_dump(),_seen=now)
    return dict(revision=store.current['revision'],clients=[{k:v for k,v in c.items() if k!='_seen'} for c in store.clients.values()])
