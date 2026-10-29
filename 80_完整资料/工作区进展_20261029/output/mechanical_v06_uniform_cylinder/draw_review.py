import json,math
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor,Color,white
O=Path(__file__).resolve().parent
D=json.loads((O/'dimensions_and_checks.json').read_text());M=D['metrics']
pdfmetrics.registerFont(TTFont('CN','/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
pdfmetrics.registerFont(TTFont('EN','/System/Library/Fonts/Supplemental/Arial.ttf'))
pdfmetrics.registerFont(TTFont('BOLD','/System/Library/Fonts/Supplemental/Arial Bold.ttf'))
W,H=1200,840
ink='#203C42'; muted='#5C7275';teal='#287C79';amber='#B17A45';pale='#E9F0ED';line='#C9D5D0';blue='#4A76A0';orange='#C07143'
C=canvas.Canvas(str(O/'器灵_通体圆柱V06_两板剑柄结构图.pdf'),pagesize=(W,H))
C.setTitle('器灵 | 圆筒外壳 V0.6 | 二维结构评审')
C.setAuthor('器灵结构设计')
def col(v):return HexColor(v)if isinstance(v,str)else v
def txt(x,y,s,size=12,c=ink,font='CN',align='left'):
 C.setFillColor(col(c));C.setFont(font,size)
 {'left':C.drawString,'center':C.drawCentredString,'right':C.drawRightString}[align](x,y,str(s))
def poly(pts,fill=None,stroke=ink,width=.7,close=True):
 C.setLineWidth(width);C.setStrokeColor(col(stroke));C.setFillColor(col(fill or white));p=C.beginPath();p.moveTo(*pts[0])
 for q in pts[1:]:p.lineTo(*q)
 if close:p.close()
 C.drawPath(p,stroke=bool(stroke),fill=bool(fill))
def rect(x,y,w,h,fill=None,stroke=ink,r=0,width=.7):
 C.setLineWidth(width);C.setStrokeColor(col(stroke));C.setFillColor(col(fill or white))
 if r:C.roundRect(x,y,w,h,r,stroke=bool(stroke),fill=bool(fill))
 else:C.rect(x,y,w,h,stroke=bool(stroke),fill=bool(fill))
def ln(a,b,c=ink,width=.7,dash=None):
 C.setStrokeColor(col(c));C.setLineWidth(width);C.setDash(dash or []);C.line(*a,*b);C.setDash([])
def circle(x,y,r,fill=None,stroke=ink,width=.7):
 C.setStrokeColor(col(stroke));C.setFillColor(col(fill or white));C.setLineWidth(width);C.circle(x,y,r,stroke=bool(stroke),fill=bool(fill))
def arrow(a,b,c=muted,size=4):
 ln(a,b,c);v=math.atan2(b[1]-a[1],b[0]-a[0]);poly([b,(b[0]-size*math.cos(v-.45),b[1]-size*math.sin(v-.45)),(b[0]-size*math.cos(v+.45),b[1]-size*math.sin(v+.45))],c,c)
def dim(a,b,label,offset=0,size=11):
 if abs(a[1]-b[1])<.1:
  aa=(a[0],a[1]+offset);bb=(b[0],b[1]+offset);ln(a,aa,line);ln(b,bb,line);arrow(aa,bb);arrow(bb,aa);txt((aa[0]+bb[0])/2,aa[1]+6,label,size,align='center')
 else:
  aa=(a[0]+offset,a[1]);bb=(b[0]+offset,b[1]);ln(a,aa,line);ln(b,bb,line);arrow(aa,bb);arrow(bb,aa);C.saveState();C.translate(aa[0]-6,(aa[1]+bb[1])/2);C.rotate(90);txt(0,0,label,size,align='center');C.restoreState()
def header(n,title,sub):
 rect(0,0,W,H,'#FAFBF8',stroke='#FAFBF8');txt(38,795,'器灵  /  CYLINDER STUDY',13,teal,font='CN');txt(38,755,title,27);txt(38,726,sub,12,muted)
 ln((38,710),(1162,710),line);ln((38,36),(1162,36),line);txt(38,18,'V0.6 · 2026-10-28 · 单位 mm · 二维评审图，尺寸以标注为准',10,muted);txt(1162,18,f'{n} / 3',10,muted,align='right')
def badge(n,x,y):circle(x,y,11,teal,teal);txt(x,y-4,f'{n:02}',9,white,font='BOLD',align='center')
def note(x,y,title,body,width=330):
 txt(x,y,title,14,ink)
 for i,s in enumerate(body):txt(x,y-23-19*i,s,11,muted)
def P(x,y,z,origin=(430,260),s=1.8):return(origin[0]+s*(.9*x+1.12*z),origin[1]+s*(y+.20*x-.22*z))
def face(coords,color,origin=(430,260),s=1.8,stroke=ink):poly([P(*a,origin,s)for a in coords],color,stroke,.65)
def box(x0,y0,z0,x1,y1,z1,color,origin=(430,260),s=1.8):
 face([(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0)],color,origin,s)
 face([(x1,y0,z0),(x1,y0,z1),(x1,y1,z1),(x1,y1,z0)],'#B6C6C2',origin,s)
 face([(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)],color,origin,s)
def disc(cx,cy,z,r,color,origin=(430,260),s=1.8):
 face([(cx+r*math.cos(t*math.pi/30),cy+r*math.sin(t*math.pi/30),z)for t in range(61)],color,origin,s)
profile=[(0,29),(2,30),(198,30),(200,29)]
def shell(shift,front):
 angles=[i*math.pi/16+(0 if front else math.pi)for i in range(17)]
 for i,(a,b)in enumerate(zip(angles,angles[1:])):
  pts=[(r*math.cos(a),y,r*math.sin(a)+shift)for y,r in profile]+[(r*math.cos(b),y,r*math.sin(b)+shift)for y,r in profile[::-1]]
  shade=0.84+0.08*math.sin(a);fill=Color(shade,shade+.025,shade+.005)
  face(pts,fill,stroke='#C1CDC7')
 for a in [angles[0],angles[-1]]:
  poly([P(r*math.cos(a),y,r*math.sin(a)+shift)for y,r in profile],None,teal,1.2,False)
 for yy,rr in [(5,30),(195,30)]:
  poly([P(rr*math.cos(a),yy,rr*math.sin(a)+shift)for a in angles],None,amber,1.5,False)
 if front:
  disc(0,177,shift+30,20,'#F8FAF7');disc(0,177,shift+30.2,16.6,'#CFDAD4')
  for yy in [24,27,30,33,36]:
   poly([P(x,yy,shift+math.sqrt(max(0,30*30-x*x)))for x in range(-7,8)],None,muted,.8,False)
def board(name,shift):
 b=D['boards'][name];dx,dy,z=b['pose'];z+=shift
 pts=b['outline'];face([(x+dx,y+dy,z+1.6)for x,y in pts],teal)
 for c in b['components']:
  if c['layer']!=1:continue
  x0,y0,x1,y1=c['body'];h=min(c['height'],7.3)
  box(x0+dx,y0+dy,z+1.6,x1+dx,y1+dy,z+1.6+h,'#E6D9BE'if c['ref'].startswith('J')else '#4D5554')
 for x,y,d in b['holes']:disc(x+dx,y+dy,z+1.7,d/2,white)
def cyl_proxy(cx,cy,cz,r,length,color):
 pts=[(cx+r*math.cos(t*math.pi/20),cy,cz+r*math.sin(t*math.pi/20))for t in range(41)]
 face(pts,color)
 for i in range(20):
  a=i*math.pi/20;b=(i+1)*math.pi/20
  face([(cx+r*math.cos(a),cy,cz+r*math.sin(a)),(cx+r*math.cos(b),cy,cz+r*math.sin(b)),(cx+r*math.cos(b),cy+length,cz+r*math.sin(b)),(cx+r*math.cos(a),cy+length,cz+r*math.sin(a))],color,stroke='#8F9B95')
 face([(x,cy+length,z)for x,y,z in pts],'#CED9CD')
def silhouette(cx,base,s=2):
 pts=[(cx-r*s,base+y*s)for y,r in profile]+[(cx+r*s,base+y*s)for y,r in profile[::-1]];poly(pts,'#DCE5DD',teal,1.2)
 for yy,rr in [(5,30),(195,30)]:ln((cx-rr*s,base+yy*s),(cx+rr*s,base+yy*s),amber,2)
 circle(cx,base+177*s,20*s,'#B78B58',amber);circle(cx,base+177*s,17*s,'#163B40',ink)
 txt(cx,base+177*s-5,'器灵',15,'#EBEEE1',align='center')
 for yy in [24,27,30,33,36]:ln((cx-7*s,base+yy*s),(cx+7*s,base+yy*s),muted,1)
 for xx in [-10,-5,0,5,10]:ln((cx+xx*s,base+48*s),(cx+xx*s,base+98*s),'#BDCFC4',.7)

header(1,'通体圆柱剑柄 · 两块 PCB 的爆炸图','整段外径一致；剑柄固定板件只有主控 ×1、电源 ×1。剑身板属于可拆剑身，不列入剑柄装配。')
rect(38,200,810,493,'#F2F5EF',stroke=line,r=14)
shell(-70,False)
box(-14,164,-105,14,192,-104,'#B48751')
# Separate removable support stations; no PCB belonging to the blade is drawn here.
for xa,xb in [(-26,-23),(21,24)]:
 for ya,yb in [(10,73),(98,130),(144,195)]:box(xa,ya,-8,xb,yb,-5,'#B4C2B7')
for ya,yb in [(73,98),(130,144)]:
 box(-26,ya,-8,-23,yb,-5,'#B4C2B7')
box(21,73,-15,23,98,-12,'#B4C2B7')
for yy in [10,130,195]:box(-26,yy,-8,24,yy+3,-5,'#B4C2B7')
for name in ['main','power']:
 b=D['boards'][name];dx,dy,z=b['pose']
 for x,y,d in b['holes']:box(x+dx-2.5,y+dy-2.5,z-3.5,x+dx+2.5,y+dy+2.5,z,'#B4C2B7')
board('power',-25);board('main',25)
cyl_proxy(0,43,38,9.55,69.2,'#9DAB97')
for yy in [53,100]:box(-10.25,yy,36,10.25,yy+4,37,'#8E9E90')
disc(0,29,42,10,'#404C48');disc(11,61,42,4.1,'#A7B3AA')
shell(70,True)
disc(0,177,130,17.9,'#173F45');disc(0,177,139,20,'#B78B58');disc(0,177,140,16.6,'#E4EBE2')
face([(-29,213,0),(29,213,0),(29,217,0),(-29,217,0)],'#B78B58')
for a,b in [((0,177,-105),(0,177,140)),((0,78,-70),(0,78,95)),((0,200,0),(0,217,0))]:ln(P(*a),P(*b),line,.7,[3,4])
for n,pt in [(1,(0,40,-92)),(2,(0,184,-108)),(3,(-24,130,-7)),(4,(0,107,-25)),(5,(0,163,28)),(6,(0,78,38)),(7,(0,35,42)),(8,(0,80,99)),(9,(0,202,140)),(10,(0,217,0))]:badge(n,*P(*pt))
txt(58,673,'剑柄分件',13,teal);txt(58,652,'爆炸位移仅用于展示装配关系',10.5,muted)
rect(872,200,290,493,white,line,r=14)
silhouette(1013,239,1.9)
dim((956,675),(1070,675),'全长同一外径 Ø60',offset=0,size=12)
dim((1080,239),(1080,619),'200',offset=37,size=12)
ln((948,619),(1078,619),orange,.8,[4,3]);arrow((1013,624),(1013,649),orange)
txt(1013,655,'剑身另装（含剑身板）',11,orange,align='center')
txt(1013,217,'通体等径；圆屏内嵌，端圈齐平',11,teal,align='center')
legend=[('后半圆壳','与前壳合成等径圆柱'),('NFC 无源线圈','固定在后盖内侧'),('可拆内骨架','主控、电源分别安装和拆卸'),('电源板 / 托架','38×48；位于主控板下方'),('主控板 / 托架','40×50；上端连接剑身接口'),('电池包 / 托杯','与电源板前后错层；双绑带'),('扬声器 / LRA','下端出声、握持区传振'),('前半圆壳','USB 凹槽及齐平电源键'),('屏幕 / 压圈','内嵌圆窗；外壳整体仍等径'),('顶部导向座','仅留对接结构；不固定剑身板')]
for i,(a,b)in enumerate(legend):
 x=48+(i%5)*226;y=162-(i//5)*68;badge(i+1,x+10,y);txt(x+27,y+2,a,11);txt(x+27,y-19,b,9.5,muted)
C.showPage()

header(2,'重新分配内部空间 · 沿长度摆放两块板','将电源板下移，与电池前后错层；主控天线区域留空。尺寸基于现有 PCB，暂定器件尺寸已单独标出。')
ox,oy,s=170,117,2.65
def A(x,y):return(ox+x*s,oy+y*s)
poly([A(-r,y)for y,r in profile]+[A(r,y)for y,r in profile[::-1]],'#EEF3EC',teal,1)
rect(*A(-25.7,144),40*s,50*s,'#C0DACE',teal)
rect(*A(-24.7,74),38*s,48*s,'#D1DFEA',blue)
rect(*A(-9.55,43),19.1*s,69.2*s,'#C5CBB1',muted,r=8)
rect(*A(-14.7,137.605),18*s,6*s,'#E1BE8F',amber)
rect(*A(-17.9,157.85),35.8*s,38.3*s,None,ink,width=1)
txt(*A(-5.7,151),'主控',10.5,teal,align='center');txt(*A(-18,117),'电源',10.5,blue,align='center');txt(*A(0,72),'电池',10.5,align='center')
circle(*A(0,29),10*s,'#BBCBC1',muted);txt(*A(0,28),'扬声器',9.5,align='center')
dim(A(-33,0),A(-33,200),'主体总长 200',offset=-20,size=12)
dim(A(-30,200),A(30,200),'Ø60',offset=22,size=12)
labels=[('剑柄 / 剑身分界 Y=200',200),('主控板 Y=144–194',188),('天线 Y≈137.6–143.6',139.5),('板边间隔 22',132),('电源板 Y=74–122',120),('电池顶 Y=112.2',106),('电池底 Y=43',43)]
for label,y in labels:
 xx,yy=A(29,y);ln((xx,yy),(280,yy),line);txt(286,yy-4,label,10.5)
txt(61,75,'主控、电源沿轴向分开，分别固定在各自托架。',11,teal)
txt(61,54,'剑身拆下时，剑身板随剑身一起离开。',11,muted)

def section(cx,cy,scale,title):
 circle(cx,cy,30*scale,'#DCE5DD',teal);circle(cx,cy,27.6*scale,'#FAFBF8',teal)
 txt(cx,cy+30*scale+23,title,15,align='center')
 def Q(x,z):return(cx+x*scale,cy+z*scale)
 return Q
Q=section(657,501,4.6,'A · 主控与屏幕区')
def qrect(Q,x,z,w,h,scale,fill,stroke=ink):rect(*Q(x,z),w*scale,h*scale,fill,stroke)
qrect(Q,-25.7,0,40,1.6,4.6,teal)
qrect(Q,7.6,1.6,5.85,7.3,4.6,'#D6C5A3');qrect(Q,13.45,1.6,8.35,7.3,4.6,'#EAD9B7')
qrect(Q,-17.9,18,35.8,1.8,4.6,'#254B50');qrect(Q,-16.6,22,33.2,1,4.6,'#9AB5B2')
qrect(Q,-14,-23,28,1,4.6,amber);qrect(Q,-14,-22,28,.5,4.6,muted)
poly([Q(x,z)for x,z in D['wire_curve']],None,orange,2,False)
txt(657,334,'内径 Ø55.2；屏幕背面至主控最高包络 9.1',10.5,align='center')
Q=section(1003,501,4.6,'B · 电源与电池区')
qrect(Q,-24.7,-9,38,1.6,4.6,blue)
qrect(Q,-24.7,-7.4,38,7.3,4.6,'#DCE7F0',blue)
circle(*Q(0,12),9.55*4.6,'#C5CBB1',muted)
qrect(Q,-11,.8,22,.5,4.6,amber)
txt(*Q(0,11),'电池',11,align='center')
txt(1003,334,'电池与最高元件预算间隙 2.55',10.5,align='center')
rect(514,76,648,233,white,line,r=14)
txt(538,278,'关键距离与接口',16)
rows=[('电源板上边 → 主控天线下端','137.605 - 122 = 15.605'),('电池上端 → 主控天线下端','137.605 - 112.2 = 25.405'),('侧插线束 → 筒内壁','最小名义净空 1.28；转弯 R4 为设计分配'),('电池槽','Ø20.5×74；电池暂按 Ø19.1×69.2'),('USB-C','退入约 16.06；插线仓 18×12×18'),('屏幕圆窗','镜片中心内凹约 7；实屏/FPC/视角待核')]
for i,(a,b)in enumerate(rows):
 y=248-i*28;txt(538,y,a,10.5,muted);txt(796,y,b,10.5)
C.showPage()

header(3,'固定方式与装配归属 · 剑柄、剑身分开','保持 PCB 的现有安装孔位；所有尺寸是结构评审值，实物包络与制造公差确认后再进入三维设计。')
rect(38,421,1124,270,white,line,r=14)
txt(62,658,'剑柄内固定件',17,teal);txt(828,658,'可拆剑身内固定件',17,orange)
rect(65,485,260,128,'#DDEAE2',teal,r=8);txt(195,581,'主控 PCB 40×50',16,align='center');txt(195,553,'孔距 32×42 / Ø2.2',12,align='center');txt(195,527,'三颗 M2 螺丝 + 一个 Ø1.9 定位销',11,align='center');txt(195,505,'定位销位于 (+16,+4)，避开 R1',10.5,muted,align='center')
rect(355,485,250,128,'#E3EBF1',blue,r=8);txt(480,581,'电源 PCB 38×48',16,align='center');txt(480,553,'孔距 30×40 / Ø2.2',12,align='center');txt(480,527,'四颗 M2 螺丝，独立托架',11,align='center');txt(480,505,'沿轴向布置在主控板下方',10.5,muted,align='center')
ln((738,447),(738,641),orange,1,[5,4]);txt(738,433,'机械拆分界面',11,orange,align='center')
rect(833,485,294,128,'#F2E7D9',amber,r=8);txt(980,581,'剑身 PCB 20×32',16,align='center');txt(980,553,'安装在剑身自己的内支架上',12,align='center');txt(980,527,'拆剑身时随剑身一起取走',12,orange,align='center');txt(980,505,'不计入剑柄 PCB 数量或固定件清单',10.5,muted,align='center')
txt(715,589,'主控 J7 ↔ 剑身 J701',10.5,align='center');txt(62,448,'顶部外壳先导向、肩部限位和锁止，再由连接器完成电气接触；插针不作为承力锁扣。',12)
rect(38,68,546,327,'#F0F4ED',line,r=14);rect(608,68,554,327,'#F0F4ED',line,r=14)
txt(62,361,'本次改正与尺寸依据',17)
lines=['外形：Ø60 通体等径，长度 200；上下端圈外径也为 Ø60。','PCB：主控和电源两块；原剑身板只保留外部接口关系。','主控/电源不再集中叠放在顶部，电池使用下半段前侧空间。','主控板 X=-5.7，Y=144，底面 Z=0。','电源板 X=-5.7，Y=74，底面 Z=-9。','支撑/紧固件对器件包络核查：重叠 0 项。','最紧内壁名义余量约 0.62；线束余量约 1.28。','Ø60 是保守包络下的试装起点，尚不是最终手感尺寸。']
for i,s in enumerate(lines):txt(62,327-i*28,s,11,ink if i<5 else muted)
txt(632,361,'进入三维设计前仍需确认',17)
lines=['屏幕：暂用 35.8×38.3×1.8；FPC 出线和接触面待核。','电池：保护板、包膜及线根必须计入 Ø19.1×69.2 包络。','连接器：未扣除未知插合重叠，继续按完整胶壳保守留量。','电源键：改为避开电池的双导向推杆，行程由实物确定。','顶部配件插合：板边距 5.3 / 插深 2.5 均暂定。','内骨架在 USB 仓处向后绕行；合壳前先接线、再固定。','来源：本地 V082 保存快照与 GHD 厂家尺寸图。','本次仅二维图纸；未修改 PCB，未生成 3D 模型。']
for i,s in enumerate(lines):txt(632,327-i*28,s,11,muted)
C.showPage();C.save()
print(O/'器灵_通体圆柱V06_两板剑柄结构图.pdf')

