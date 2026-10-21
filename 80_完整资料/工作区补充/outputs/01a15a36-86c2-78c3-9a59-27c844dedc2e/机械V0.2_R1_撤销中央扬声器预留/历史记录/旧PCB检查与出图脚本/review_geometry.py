import json,math
from pathlib import Path
from shapely.geometry import Polygon,box,Point
from shapely import affinity
from shapely.ops import unary_union
ROOT=Path(__file__).resolve().parent
DATA=json.loads((ROOT/'review-v072-sync.json').read_text())['value']
COMPS={c['ref']:{**c['component'],'ref':c['ref'],'id':c['id']} for c in DATA['components']}
def parse_source(s):
    out=[]
    for l in s.splitlines():
        if '||' not in l:continue
        a,b=l.split('||',1)
        try:out.append((json.loads(a),json.loads(b.rstrip('|'))))
        except ValueError:pass
    return out
DOCS={k:{'records':v} for k,v in json.loads((ROOT/'review-20261021-docs.json').read_text()).items() if v[0][1].get('docType')=='FOOTPRINT'}
MM=.0254

def path_points(path):
    if not path:return []
    if path[0]=='R':
        _,x,y,w,h,*_=path
        return [(x,y),(x+w,y),(x+w,y-h),(x,y-h)]
    if path[0]=='CIRCLE':
        _,x,y,r,*_=path
        return [(x-r,y-r),(x+r,y+r)]
    out=[];i=0
    while i<len(path):
        if isinstance(path[i],str):
            cmd=path[i];i+=1
            if cmd in ['ARC','CARC']:i+=1
            continue
        if i+1<len(path)and isinstance(path[i+1],(int,float)):
            out.append((path[i],path[i+1]));i+=2
        else:i+=1
    return out

def pad_polygon(b):
    d=b['defaultPad'];cx=b['centerX'];cy=b['centerY'];t=d['padType']
    if t=='POLYGON':
        points=path_points(d['path'])
        p=Polygon(points)if len(points)>=3 else Point(cx,cy).buffer(1)
        if not p.is_valid:p=p.buffer(0)
    else:
        w=d.get('width',0);h=d.get('height',w)
        p=box(cx-w/2,cy-h/2,cx+w/2,cy+h/2)
        p=affinity.rotate(p,b.get('padAngle',0),origin=(cx,cy))
    return affinity.scale(p,xfact=MM,yfact=MM,origin=(0,0))

LOCAL={}
for ref,c in COMPS.items():
    d=DOCS[c['footprint']['uuid']];pads=[];thr=[];bodypts=[];silkpts=[]
    for a,b in d['records']:
        if a['type']=='PAD':
            poly=pad_polygon(b);pads.append((b['num'],poly,b))
            if b.get('layerId')==12:thr.append(poly)
        if a['type']=='FILL'and b.get('layerId')==12:
            for path in b.get('path',[]):
                if path[0]=='CIRCLE':
                    _,x,y,r,*_=path;thr.append(Point(x*MM,y*MM).buffer(r*MM))
                else:
                    pts=path_points(path)
                    if len(pts)>=3:thr.append(affinity.scale(Polygon(pts),xfact=MM,yfact=MM,origin=(0,0)))
        if a['type']=='POLY'and b.get('layerId')in[48,3]:
            pts=path_points(b.get('path',[]))
            if b.get('path',[None])[0]=='CIRCLE':continue
            (bodypts if b.get('layerId')==48 else silkpts).extend(pts)
    pts=bodypts or silkpts
    if pts:
        body=box(min(p[0]for p in pts)*MM,min(p[1]for p in pts)*MM,max(p[0]for p in pts)*MM,max(p[1]for p in pts)*MM)
    else:body=unary_union([p for _,p,_ in pads]).convex_hull
    # Jumper references are bare plated holes, not populated tall headers.
    if ref in ['J102','J103','J106','J107']:body=unary_union([p for _,p,_ in pads]).convex_hull
    courtyard=unary_union([body]+[p for _,p,_ in pads]).convex_hull
    LOCAL[ref]={'body':body,'pads':pads,'courtyard':courtyard,'through':unary_union(thr)if thr else None}

def transform(p,x,y,rotation,layer):
    if layer==2:p=affinity.scale(p,xfact=1,yfact=-1,origin=(0,0))
    return affinity.translate(affinity.rotate(p,rotation,origin=(0,0)),xoff=x,yoff=y)

def shapes(ref,x,y,rotation,layer):
    d=LOCAL[ref]
    return {k:transform(d[k],x,y,rotation,layer)if d[k] is not None else None for k in ['body','courtyard','through']}

BOARD=Polygon([(-17,36),(17,36),(17,141),(9.8,141),(9.8,134.5),(-9.8,134.5),(-9.8,141),(-17,141)])
SPEAKER=box(-13,67,13,93)
if __name__=='__main__':
 for ref in COMPS:
  if ref[0] in ['U','J','L','Q','F']:
   print(ref,'body',tuple(round(x,3)for x in LOCAL[ref]['body'].bounds),'court',tuple(round(x,3)for x in LOCAL[ref]['courtyard'].bounds))
