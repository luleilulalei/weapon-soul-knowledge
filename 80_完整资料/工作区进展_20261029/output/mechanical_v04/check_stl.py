from pathlib import Path
import json,struct,hashlib
from collections import Counter,defaultdict
import numpy as np
O=Path('output/mechanical_v04');out=[]
for p in sorted((O/'model/stl').glob('*.stl')):
 raw=p.read_bytes();n=struct.unpack_from('<I',raw,80)[0];assert len(raw)==84+50*n
 dtype=np.dtype([('normal','<f4',3),('vertices','<f4',(3,3)),('attr','<u2')]);tris=np.frombuffer(raw,offset=84,dtype=dtype)['vertices'].astype(float)
 verts,idx=np.unique(np.round(tris.reshape(-1,3),5),axis=0,return_inverse=True);faces=idx.reshape(-1,3)
 edges=Counter();adj=defaultdict(set)
 for a,b,c in faces:
  for x,y in [(a,b),(b,c),(c,a)]:edges[tuple(sorted((int(x),int(y))))]+=1;adj[int(x)].add(int(y));adj[int(y)].add(int(x))
 unseen=set(adj);cc=0
 while unseen:
  cc+=1;todo=[unseen.pop()]
  while todo:
   for v in adj[todo.pop()]:
    if v in unseen:unseen.remove(v);todo.append(v)
 volume=abs(float(np.einsum('ij,ij->i',tris[:,0],np.cross(tris[:,1],tris[:,2])).sum()/6))
 lo=verts.min(axis=0);hi=verts.max(axis=0)
 out.append(dict(file=p.name,triangles=n,boundary_or_nonmanifold_edges=sum(v!=2 for v in edges.values()),connected_components=cc,volume_mm3=volume,print_bbox_mm=(hi-lo).tolist(),minimum_z_mm=float(lo[2]),sha256=hashlib.sha256(raw).hexdigest()))
(O/'verification/stl_independent.json').write_text(json.dumps(out,indent=2))
print('STL_COUNT',len(out));print('ISSUES',[x for x in out if x['boundary_or_nonmanifold_edges'] or x['connected_components']!=1 or abs(x['minimum_z_mm'])>.001 or x['volume_mm3']<=0])
