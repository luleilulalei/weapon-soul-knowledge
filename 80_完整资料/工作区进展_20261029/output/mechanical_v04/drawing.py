import json,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
O=Path('output/mechanical_v04');d=json.load(open(O/'model/pcb_input.json'))
font='/System/Library/Fonts/STHeiti Medium.ttc'
def f(n):return ImageFont.truetype(font,n)
im=Image.new('RGB',(1500,1200),'#f4f7f9');g=ImageDraw.Draw(im)
g.text((70,40),'器灵内核  ·  V0.4 结构基准',font=f(42),fill='#112a3c');g.text((70,105),'适配 V074P3B 主板 / V0.2 适配板    单位 mm    2026.10.26',font=f(24),fill='#546b7a')
scale=10.7
pt=lambda x,y:(430+x*scale,1010-(y-80)*scale)
g.polygon([pt(x,y)for x,y in d['outline']],fill='#d7ece7',outline='#0b645a',width=4)
for c in d['components']:
 x0,y0,x1,y1=c['bbox_xy'];g.rectangle([pt(x0,y1),pt(x1,y0)],fill='#aed5c9'if c['placement']['layer']==1 else '#d4e1e8',outline='#668c87',width=1)
for i,(x,y)in enumerate(d['holes']):
 X,Y=pt(x,y);r=1.1*scale;g.ellipse((X-r,Y-r,X+r,Y+r),fill='white',outline='#0f6371',width=3);g.line((X-23,Y,X+23,Y),fill='#1f7f90',width=1);g.line((X,Y-23,X,Y+23),fill='#1f7f90',width=1)
 g.text((X+20,Y-18),f'H{i+1}',font=f(21),fill='#0c4659')
def dim(a,b,label,offset):
 A=pt(*a);B=pt(*b);A=(A[0]+offset[0],A[1]+offset[1]);B=(B[0]+offset[0],B[1]+offset[1]);g.line([A,B],fill='#286477',width=2)
 if abs(A[1]-B[1])<1:
  for p in [A,B]:g.line((p[0],p[1]-10,p[0],p[1]+10),fill='#286477',width=2)
  g.text(((A[0]+B[0])/2-45,A[1]-40),label,font=f(24),fill='#124358')
 else:
  for p in [A,B]:g.line((p[0]-10,p[1],p[0]+10,p[1]),fill='#286477',width=2)
  g.text((A[0]-85,(A[1]+B[1])/2-15),label,font=f(24),fill='#124358')
dim((-19,146.5),(19,146.5),'38.0',(0,-85));dim((-19,85),(-19,146.5),'61.5',(-85,0))
g.text((195,1120),'主板原生坐标：Y=80 至 151.5；四孔 Ø2.2',font=f(23),fill='#335467')
notes=[('01  四凸耳主板固定','孔中心 X = ±19；Y = 85 / 146.5','总装 Y = 原生 Y + 27.5，板底 Z = 0'),('02  保留主体比例','主体 190 × 62 × 40；握持区宽 46','顶部局部加宽至 51，给凸耳和接口让位'),('03  新六针对接件','主板母座 + 适配板公头，PCB 平行','导向先于插针；肩部止挡 + 两颗固定螺丝'),('04  调节后再冻结','插入深度 2.5 为暂定装配值','板位沿轴 ±0.6；0.3 垫片用于试配'),('05  审核边界','XY 来自最新保存的 PCB 原生数据','器件高度、实屏/FPC、锁止承力仍需实物验证')]
y=220
for title,a,b in notes:
 g.text((875,y),title,font=f(29),fill='#123747');g.text((875,y+48),a,font=f(21),fill='#4c6576');g.text((875,y+82),b,font=f(21),fill='#4c6576');y+=166
im.save(O/'renders/07_datums.png')
