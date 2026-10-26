from fastapi import APIRouter,HTTPException
from fastapi.responses import Response
from app.core import unity_active

router=APIRouter()

@router.get('/active.json')
def active(response:Response):
    response.headers['Cache-Control']='no-store'
    try:return unity_active.active()
    except (OSError,ValueError,KeyError) as error:raise HTTPException(503,'尚无可用的Unity结果') from error

@router.get('/runs/{identity}/replay.json')
def replay(identity:str):
    try:return Response(unity_active.run_bytes(identity),media_type='application/json',headers={'Cache-Control':'no-store'})
    except OSError as error:raise HTTPException(404,'运行快照不存在') from error
