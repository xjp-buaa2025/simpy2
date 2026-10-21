"""Optional LAN image relay. No scheduling, playback clock, files or frame queue."""
import re
import struct
import threading
import time
from collections import deque
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter()
MAX_BYTES = 262144
TARGET_FPS = 20
MAX_UPLOAD_FPS = 30


def jpeg_size(data):
    if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
        raise ValueError('Expected a JPEG image')
    at = 2
    while at + 4 <= len(data):
        if data[at] != 255:
            break
        while at < len(data) and data[at] == 255:
            at += 1
        marker = data[at]
        at += 1
        if marker in (0xD9, 0xDA):
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        length = struct.unpack('>H', data[at:at + 2])[0]
        if length < 2 or at + length > len(data):
            break
        if marker in (0xC0, 0xC1, 0xC2) and length >= 8:
            height, width = struct.unpack('>HH', data[at + 3:at + 7])
            if 16 <= width <= 1280 and 16 <= height <= 720:
                return width, height
            raise ValueError('Maximum frame dimensions are 1280 x 720')
        at += length
    raise ValueError('JPEG dimensions missing or invalid')


class Relay:
    def __init__(self, now=time.monotonic):
        self.now = now
        self.lock = threading.RLock()
        self.viewers = {}
        self.publisher = ''
        self.publisher_until = 0
        self.source = ''
        self.detail = ''
        self.frame = b''
        self.frame_at = -999
        self.sequence = -1
        self.width = self.height = 0
        self.frame_times = deque(maxlen=MAX_UPLOAD_FPS)

    def validate_id(self, value):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', value):
            raise HTTPException(400, 'Invalid client identifier')

    def state(self):
        with self.lock:
            now = self.now()
            self.viewers = {k: v for k, v in self.viewers.items() if v > now}
            age = now - self.frame_at
            connected = self.publisher_until > now
            return dict(schema_version=1, demand=bool(self.viewers), connected=connected,
                        live=connected and bool(self.frame) and age < 2,
                        publisher_id=self.publisher if connected else '', source=self.source,
                        detail=self.detail, sequence=self.sequence, width=self.width, height=self.height,
                        frame_age_ms=round(age * 1000) if self.frame else -1,
                        target_fps=TARGET_FPS, max_bytes=MAX_BYTES)

    def viewer(self, client, active):
        self.validate_id(client)
        with self.lock:
            if active:
                self.state()
                if client not in self.viewers and len(self.viewers) >= 16:
                    raise HTTPException(429, 'Too many viewers')
                self.viewers[client] = self.now() + 3
            else:
                self.viewers.pop(client, None)
            return self.state()

    def claim(self, client):
        self.validate_id(client)
        now = self.now()
        if self.publisher and client != self.publisher and self.publisher_until > now:
            raise HTTPException(409, 'Another headset is publishing')
        if client != self.publisher:
            self.frame = b''
            self.sequence = -1
            self.frame_at = -999
            self.frame_times.clear()
        self.publisher = client
        self.publisher_until = now + 3

    def status(self, client, source, detail):
        with self.lock:
            self.claim(client)
            if source != self.source or source == 'unavailable':
                self.frame = b''
            self.source, self.detail = source, detail
            return self.state()

    def publish(self, client, sequence, image):
        width, height = jpeg_size(image)
        with self.lock:
            self.claim(client)
            if not self.state()['demand']:
                raise HTTPException(409, 'No active PC viewer')
            if sequence <= self.sequence:
                raise HTTPException(409, 'Out of order frame')
            frame_now = self.now()
            while self.frame_times and frame_now - self.frame_times[0] >= 1:
                self.frame_times.popleft()
            # A bounded timestamp window allows ordinary transport jitter without a frame queue.
            if len(self.frame_times) >= MAX_UPLOAD_FPS or self.frame and frame_now - self.frame_at < 1 / (MAX_UPLOAD_FPS * 2):
                raise HTTPException(429, 'Frame rate limit', headers={'Retry-After': '0.05'})
            self.frame, self.sequence, self.frame_at = image, sequence, frame_now
            self.frame_times.append(frame_now)
            self.width, self.height = width, height
            return self.state()

    def read(self, after, publisher_id=''):
        with self.lock:
            state = self.state()
            if not state['live']:
                return Response(status_code=204, headers={'Cache-Control': 'no-store'})
            if after == self.sequence and publisher_id == self.publisher:
                return Response(status_code=304, headers={'Cache-Control': 'no-store'})
            return Response(self.frame, media_type='image/jpeg', headers={
                'Cache-Control': 'no-store', 'X-Frame-Sequence': str(self.sequence),
                'X-Frame-Age-Ms': str(state['frame_age_ms']), 'X-Publisher-Id': self.publisher,
                'X-Mirror-Source': self.source, 'X-Frame-Width': str(self.width), 'X-Frame-Height': str(self.height)})


relay = Relay()


class HostLeases:
    """Only desktop clients keep a managed helper alive; headset heartbeats do not."""
    def __init__(self, now=time.monotonic):
        self.now = now
        self.clients = {}
        self.lock = threading.RLock()
        self.ever_registered = False

    def update(self, client, active):
        relay.validate_id(client)
        with self.lock:
            if active:
                self.ever_registered = True
                self.clients[client] = self.now() + 12
            else:
                self.clients.pop(client, None)
            return self.count()

    def count(self):
        with self.lock:
            self.clients = {k:v for k,v in self.clients.items() if v > self.now()}
            return len(self.clients)


hosts = HostLeases()
managed_service = False


class Host(BaseModel):
    client_id: str = Field(max_length=64)
    active: bool = True


@router.get('/service')
def service_info():
    return dict(protocol_version=1, managed=managed_service, host_count=hosts.count())


@router.post('/host')
def host_heartbeat(body: Host):
    return dict(protocol_version=1, managed=managed_service, host_count=hosts.update(body.client_id, body.active))


class Viewer(BaseModel):
    viewer_id: str = Field(max_length=64)
    active: bool


class Publisher(BaseModel):
    publisher_id: str = Field(max_length=64)
    source: str = Field(default='xr_left_eye', pattern='^(xr_left_eye|editor_test|unavailable)$')
    detail: str = Field(default='', max_length=160)


@router.get('/state')
def state():
    return relay.state()


@router.post('/viewer')
def viewer(body: Viewer):
    return relay.viewer(body.viewer_id, body.active)


@router.post('/publisher')
def publisher(body: Publisher):
    return relay.status(body.publisher_id, body.source, body.detail)


@router.post('/frame')
async def frame(request: Request, publisher_id: str, sequence: int):
    if sequence < 0:
        raise HTTPException(400, 'Invalid sequence')
    if request.headers.get('content-type', '').split(';')[0] != 'image/jpeg':
        raise HTTPException(415, 'Expected image/jpeg')
    image = bytearray()
    async for part in request.stream():
        if len(image) + len(part) > MAX_BYTES:
            raise HTTPException(413, 'Frame exceeds 256 KiB')
        image.extend(part)
    try:
        return relay.publish(publisher_id, sequence, bytes(image))
    except (ValueError, IndexError, struct.error) as error:
        raise HTTPException(400, str(error))


@router.get('/frame.jpg')
def latest_frame(after: int = -1, publisher_id: str = ''):
    return relay.read(after, publisher_id)
