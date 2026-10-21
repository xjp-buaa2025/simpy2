import urllib.request,io,zipfile,json,pathlib,time,hashlib
URL='https://zenodo.org/records/5356992/files/Television_AssemblyPackaging.zip?download=1'
OUT=pathlib.Path('.cache/industrial_assembly_20261019');OUT.mkdir(exist_ok=True)
class Remote(io.RawIOBase):
    def __init__(self):self.pos=0;self.size=561462098;self.cache=[]
    def seekable(self):return True
    def seek(self,n,w=0):self.pos=n if w==0 else self.pos+n if w==1 else self.size+n;return self.pos
    def tell(self):return self.pos
    def read(self,n=-1):
        if n<0:n=self.size-self.pos
        n=min(n,self.size-self.pos)
        if n<=0:return b''
        for start,b in self.cache:
            if start<=self.pos and self.pos+n<=start+len(b):d=b[self.pos-start:self.pos-start+n];self.pos+=n;return d
        start=self.pos;length=min(max(n,65536),self.size-start)
        for attempt in range(4):
            try:
                req=urllib.request.Request(URL,headers={'Range':f'bytes={start}-{start+length-1}'})
                with urllib.request.urlopen(req,timeout=40) as r:
                    assert r.status==206 and r.headers['Content-Range'].startswith(f'bytes {start}-'),r.headers
                    d=r.read()
                assert len(d)==length;break
            except Exception:
                if attempt==3:raise
                time.sleep(1+attempt)
        self.cache.append((start,d));self.pos+=n;return d[:n]
with zipfile.ZipFile(Remote()) as z:
    entries=[{'name':a.filename,'size':a.file_size,'compressed':a.compress_size} for a in z.infolist()];(OUT/'zip_entries.json').write_text(json.dumps(entries,indent=2))
    candidates=[a for a in entries if a['name'].lower().endswith('.bvh') and ('TV_' in a['name'] or 'TVB' in a['name'])]
    print('candidates',[(a['name'],a['size']) for a in candidates[:22]],flush=True)
    selected=[a for a in candidates if 'S01P01R01' in a['name'] and 'TV_' in a['name'] or 'S01P03R01' in a['name'] and 'TVB' in a['name']]
    for a in selected:
        name=pathlib.Path(a['name']).name;p=OUT/name
        if not p.exists():p.write_bytes(z.read(a['name']))
        print('downloaded',name,p.stat().st_size,flush=True)
    metadata=json.load(urllib.request.urlopen('https://zenodo.org/api/records/5356992'))
    (OUT/'SOURCE.json').write_text(json.dumps({'record':metadata,'selected':[{**a,'sha256':hashlib.sha256((OUT/pathlib.Path(a['name']).name).read_bytes()).hexdigest()} for a in selected]},ensure_ascii=False,indent=2),encoding='utf-8')
