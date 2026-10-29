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
C=canvas.Canvas(str(O/'器灵_圆筒外壳V05_爆炸图与尺寸核算.pdf'),pagesize=(W,H))
C.setTitle('器灵 | 圆筒外壳 V0.5 | 二维结构评审')
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
 ln((38,710),(1162,710),line);ln((38,36),(1162,36),line);txt(38,18,'V0.5 · 2026-10-28 · 单位 mm · 二维评审图，尺寸以标注为准',10,muted);txt(1162,18,f'{n} / 4',10,muted,align='right')
def badge(n,x,y):circle(x,y,11,teal,teal);txt(x,y-4,f'{n:02}',9,white,font='BOLD',align='center')
def note(x,y,title,body,width=330):
 txt(x,y,title,14,ink)
 for i,s in enumerate(body):txt(x,y-23-19*i,s,11,muted)
def P(x,y,z,origin=(445,248),s=1.8):return(origin[0]+s*(.9*x+1.12*z),origin[1]+s*(y+.20*x-.22*z))
def face(coords,color,origin=(445,248),s=1.8,stroke=ink):poly([P(*a,origin,s)for a in coords],color,stroke,.65)
def box(x0,y0,z0,x1,y1,z1,color,origin=(445,248),s=1.8):
 face([(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0)],color,origin,s)
 face([(x1,y0,z0),(x1,y0,z1),(x1,y1,z1),(x1,y1,z0)],'#B6C6C2',origin,s)
 face([(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)],color,origin,s)
def disc(cx,cy,z,r,color,origin=(445,248),s=1.8):
 face([(cx+r*math.cos(t*math.pi/30),cy+r*math.sin(t*math.pi/30),z)for t in range(61)],color,origin,s)
profile=[(0,18),(4,20),(118,20),(122,21.2),(128,26),(134,31),(136,32),(212,32),(218,29)]
def shell(shift,front):
 angles=[i*math.pi/16+(0 if front else math.pi)for i in range(17)]
 for i,(a,b)in enumerate(zip(angles,angles[1:])):
  pts=[(r*math.cos(a),y,r*math.sin(a)+shift)for y,r in profile]+[(r*math.cos(b),y,r*math.sin(b)+shift)for y,r in profile[::-1]]
  shade=0.84+0.08*math.sin(a);fill=Color(shade,shade+.025,shade+.005)
  face(pts,fill,stroke='#C1CDC7')
 for a in [angles[0],angles[-1]]:
  poly([P(r*math.cos(a),y,r*math.sin(a)+shift)for y,r in profile],None,teal,1.2,False)
 for yy,rr in [(8,20),(113,20),(208,32)]:
  poly([P(rr*math.cos(a),yy,rr*math.sin(a)+shift)for a in angles],None,amber,1.5,False)
 if front:
  disc(0,177,shift+32,20,'#F8FAF7');disc(0,177,shift+32.2,16.6,'#CFDAD4')
  for yy in [24,27,30,33,36]:
   poly([P(x,yy,shift+math.sqrt(max(0,20*20-x*x)))for x in range(-7,8)],None,muted,.8,False)
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
 for yy,rr in [(8,20),(112,20),(208,32)]:ln((cx-rr*s,base+yy*s),(cx+rr*s,base+yy*s),amber,2)
 circle(cx,base+177*s,20*s,'#B78B58',amber);circle(cx,base+177*s,17*s,'#163B40',ink)
 txt(cx,base+177*s-5,'器灵',15,'#EBEEE1',align='center')
 for yy in [24,27,30,33,36]:ln((cx-7*s,base+yy*s),(cx+7*s,base+yy*s),muted,1)
 for xx in [-10,-5,0,5,10]:ln((cx+xx*s,base+48*s),(cx+xx*s,base+98*s),'#BDCFC4',.7)

header(1,'圆筒握持外壳 · 分件爆炸图','采用 Ø40 握柄 + Ø64 上端电子仓；两板独立固定，前后半圆壳可打开检修。')
rect(38,200,820,493,'#F2F5EF',stroke='#DCE5DD',r=14)
shell(-72,False)
box(-14,169,-108,14,197,-107,'#B48751')
box(-15,168,-106,15,198,-105,'#D0D3C8')
# Open internal carrier: two upper side rails and separate battery cradle.
box(-26,138,-12,-23,210,-9,'#B4C2B7')
for ya,yb in [(138,157),(179,210)]:box(22,ya,-12,25,yb,-9,'#B4C2B7')
box(22,157,-16,24,179,-13,'#B4C2B7')
for ya,yb in [(155,158),(178,181)]:box(22,ya,-16,24,yb,-9,'#B4C2B7')
for x0,x1 in [(-13,-10),(10,13)]:box(x0,41,-10,x1,115,-7,'#B4C2B7')
box(-13,41,-10,13,44,-7,'#B4C2B7');box(-13,112,-10,13,115,-7,'#B4C2B7')
for x0 in [-13,10]:face([(x0,115,-9),(x0+3,115,-9),(25 if x0>0 else -23,138,-9),(22 if x0>0 else -26,138,-9)],'#B4C2B7')
for n in ['main','power']:
 b=D['boards'][n];dx,dy,z=b['pose']
 for x,y,d in b['holes']:box(x+dx-2.5,y+dy-2.5,-8,x+dx+2.5,y+dy+2.5,-5,'#B4C2B7')
board('power',-25);board('main',25)
cyl_proxy(0,43,28,9.55,69.2,'#9DAB97')
disc(0,31,33,10,'#404C48');disc(10,80,31,4.1,'#A7B3AA')
shell(73,True)
disc(0,177,132,17.9,'#173F45');disc(0,177,139,20,'#B78B58');disc(0,177,140,16.6,'#E4EBE2')
# End collar and optional blade module beyond the body.
board('blade',0)
face([(-15,226,0),(15,226,0),(15,234,0),(-15,234,0)],'#B78B58')
for a,b in [((0,177,-100),(0,177,142)),((0,78,-72),(0,78,92)),((0,218,0),(0,234,0))]:ln(P(*a),P(*b),line,.8,[4,4])
for n,pt in [(1,(0,55,-90)),(2,(0,186,-112)),(3,(-23,129,-10)),(4,(0,188,-25)),(5,(0,159,31)),(6,(0,78,28)),(7,(0,42,34)),(8,(0,94,94)),(9,(0,202,140)),(10,(0,234,0))]:badge(n,*P(*pt))
txt(58,674,'装配分层示意',13,teal);txt(58,653,'爆炸距离仅用于看清分件',11,muted)
rect(880,200,282,493,white,stroke=line,r=14)
silhouette(1015,233,1.8)
dim((1015-57.6,233+198*1.8),(1015+57.6,233+198*1.8),'Ø64',offset=53)
dim((979,360),(1051,360),'Ø40',offset=-20)
dim((1078,233),(1078,233+218*1.8),'218 主体长度',offset=38)
txt(1019,214,'正视轮廓 / 不含外接剑身',11,muted,align='center')
legend=[('后半圆壳','NFC 扫卡面及走线扣位'),('NFC 无源线圈','暂按 28×28；朝向外壳'),('可拆内部骨架','上下止挡承力，PCB 分托架安装'),('电源板及托架','38×48；相对主控上移 20'),('主控板及托架','40×50；3 螺丝 + 1 定位销'),('电池包及托杯','暂按 Ø19.1×69.2；绑带限位'),('扬声器 / LRA','下端出声，握持区贴壳传振'),('前半圆壳','圆屏窗、侧键及凹入式 USB 仓'),('屏幕及可换压圈','屏尺寸待核；留 3.1 后方净空'),('顶部导向 / 配件模块','止挡肩承力；插针只做电连接')]
for i,(a,b)in enumerate(legend):
 x=48+(i%5)*226;y=162-(i//5)*68;badge(i+1,x+10,y);txt(x+27,y+2,a,11);txt(x+27,y-19,b,9.5,muted)
C.showPage()

header(2,'横截面包络 · 为什么上端采用 Ø64','采用现有侧插连接器，并给插头、线束转弯及装配误差留空间；不是仅按裸 PCB 宽度定筒径。')
cx,cy,sc=315,413,7.25
def Q(x,z):return(cx+x*sc,cy+z*sc)
circle(cx,cy,32*sc,'#DCE5DD',teal,1.1);circle(cx,cy,29.6*sc,'#FAFBF8',teal,1)
ln(Q(-33,0),Q(33,0),line,.6,[4,3]);ln(Q(0,-33),Q(0,33),line,.6,[4,3])
def qr(x,z,w,h,fill,stroke=ink):rect(*Q(x,z),w*sc,h*sc,fill,stroke,.0,.7)
qr(-24,6,40,1.6,teal);qr(-23,-8.4,38,1.6,blue)
qr(-23,-6.8,38,7.3,'#DCE7F0',blue);qr(-24,2,40,4,'#DFEBDF',teal)
qr(9.3,7.6,5.85,7.3,'#D6C5A3');qr(15.15,7.6,8.35,7.3,'#EAD9B7')
qr(8.3,-6.8,5.85,7.3,'#D6C5A3')
qr(-17.9,18,35.8,1.8,'#254B50');qr(-18.5,19.8,37,1.8,'#C8D7D0')
qr(-14,-25.5,28,1,'#B48751');qr(-14,-24.5,28,.5,'#7A827C')
pts=[Q(23.5+4*math.sin(i*math.pi/200),6.9+4*math.cos(i*math.pi/200))for i in range(101)]
poly(pts,None,orange,2.5,False);ln(pts[-1],Q(27.5,-1),orange,2.5)
txt(*Q(-20,8.6),'主控 PCB',11,teal);txt(*Q(-20,-11),'电源 PCB',11,blue)
txt(cx,cy+25*sc,'屏幕 / 软垫 / 透镜',11,align='center');txt(cx,cy-22.5*sc,'NFC 线圈 + 铁氧体预留',11,align='center')
dim(Q(-32,-33),Q(32,-33),'外径 Ø64',offset=-10,size=12)
dim(Q(-29.6,-29.6),Q(29.6,-29.6),'内径 Ø59.2',offset=-6,size=11)
dim(Q(-26,-6.8),Q(-26,6),'板面净距 12.8',offset=-25,size=11)
dim(Q(-4,.5),Q(-4,2),'1.5',offset=0,size=10)
txt(64,105,'这是沿长度方向叠合后的最大包络投影；不表示所有器件位于同一个截面。',11,muted)
txt(64,83,'Z 朝屏幕为正；PCB 横向偏移 -4。当前屏组件深置，镜片中心距圆筒表面约 10.4。',10.5,muted)
txt(64,63,'屏幕为占位尺寸，前盖圆窗需做导向斜面；视角与压圈高度待实屏确认。',10.5,orange)
rect(625,133,537,559,white,line,r=14)
txt(650,659,'尺寸链（当前设计分配）',18)
rows=[('主控板底面 / 顶面','Z = +6.0 / +7.6'),('电源板底面 / 顶面','Z = -8.4 / -6.8'),('两板相向裸板面净距','6.0 - (-6.8) = 12.8'),('相向元件保守余量','12.8 - 4.0 - 7.3 = 1.5'),('屏幕背面至主控最高包络','18.0 - (7.6 + 7.3) = 3.1'),('主控 / 电源支撑孔距','32×42 / 30×40，孔 Ø2.2'),('壳壁名义厚度','2.4；试装件尺寸误差另行校准'),('NFC 铁氧体至背面元件 / 紧固件','总包络按 ≥9.7 分配（含螺丝尾端）')]
for i,(a,b)in enumerate(rows):
 y=620-i*45;txt(650,y,a,11,muted);txt(650,y-19,b,13);ln((650,y-27),(1134,y-27),line,.5)
txt(650,223,'连接器 + 线束决定筒径',14,teal)
txt(650,200,'按完整胶壳长度 8.35、单线转弯 R4、线外径 1.0 分配。',11)
txt(650,180,'所需外径 ≈ 63.78 → 取 Ø64；线束到内壁最小约 0.61。',11)
txt(650,160,'0.61 是名义净空，胶壳实物 / 线束形态未确认，不能再直接缩径。',10.5,orange)
C.showPage()

header(3,'轴向距离 · 接口与电池空间','下端为坐标 Y=0；电子件位置按当前 PCB 的器件包络计算，电池及屏幕为待实物核对的占位。')
# Front axial envelope diagram
ox,oy,s=220,120,2.43
def A(x,y):return(ox+x*s,oy+y*s)
poly([A(-r,y)for y,r in profile]+[A(r,y)for y,r in profile[::-1]],'#EEF3EC',teal,1)
for yy in [8,118,136,210,218]:ln(A(-35,yy),A(35,yy),line,.6,[3,3])
rect(*A(-24,136),40*s,50*s,'#BED8CF',teal);rect(*A(-23,156),38*s,48*s,None,blue,width=1.4)
rect(*A(-9.55,43),19.1*s,69.2*s,'#B1BBA4',muted,r=9)
rect(*A(-13,129.605),18*s,6*s,'#E1BE8F',amber)
rect(*A(-17.9,157.85),35.8*s,38.3*s,None,ink,width=1.1)
circle(*A(0,31),10*s,'#BBCBC1',muted)
txt(*A(0,75),'电池包',12,align='center');txt(*A(-4,145),'主控板',11,teal,align='center')
txt(*A(0,193),'屏幕',11,align='center');txt(*A(0,31),'扬声器',10,align='center')
for label,y,x in [('Y=218 主体顶端',218,290),('电源上端 Y=204',204,323),('主控上端 Y=186',186,290),('电源下端 Y=156',156,323),('主控下端 Y=136',136,290),('天线伸出板边 6.40',130,320),('电池顶 Y=112.2',112.2,290),('电池底 Y=43',43,290)]:
 xx,yy=A(25,y);ln((xx,yy),(x+50,yy),muted,.6);txt(x+55,yy-4,label,10.5)
dim(A(-39,8),A(-39,118),'可握持直段 110',offset=-18,size=12)
dim(A(-39,118),A(-39,136),'过渡 18',offset=-18,size=10)
dim(A(-39,136),A(-39,218),'上端区 82',offset=-18,size=11)
txt(63,74,'电池与天线轴向间隔 17.41；电源板起点与天线末端间隔 20.39。',11)
txt(63,54,'天线区不安排金属紧固件；电池线走后侧通道。',11,muted)
# USB detail top right
rect(613,395,549,298,white,line,r=14);txt(637,660,'USB-C 插线仓：必须预留插头外壳进入空间',16)
u0x,u0y,k=735,550,7
def U(x,z):return(u0x+x*k,u0y+z*k)
rect(*U(-4,-8.4),19*k,1.6*k,blue,blue)
rect(*U(9.5,-6.8),5.6*k,3.4*k,'#C3CCC7',ink)
rect(*U(15.1,-9.9),15*k,9.6*k,'#E7CDAA',amber,r=3)
txt(*U(18,-4.7),'USB 插头',10)
ln(U(31.59,-12),U(31.59,3),teal,2)
ln(U(29.19,-12),U(29.19,3),teal,1)
txt(1052,580,'壳体外表面',10,teal)
dim(U(15.1,4),U(31.59,4),'退入约 16.50',offset=12)
txt(637,438,'开口暂定 18（轴向）×12（高度）×18（深），入口倒圆 R2。',11)
txt(637,416,'按插头塑胶外壳 ≤17×10 预留；此位置内骨架须让开，需试插确认。',10.5,orange)
rect(613,92,549,283,white,line,r=14);txt(637,344,'电池、射频与线缆的留量',16)
data=[('电池槽','Ø20.5×74；相对 Ø19.1×69.2 包：径向 0.70 / 端部合计 4.80'),('电池固定','独立托杯 + 两处柔性绑带 + 端部软垫；不靠压 PCB 限位'),('16 针板间线','端子压接点间暂定 80；两端各留检修余量，线束先插后合壳'),('屏幕 FPC','左侧沿圆弧导向，宽 8、预留 R2；实际长度 / 接触面待核'),('NFC 同轴','后侧独立通道，暂预留 50–70 路径；最终长度参与天线调谐'),('电源按键','左侧独立拨片预留 20×8×6；驱动 SW4，行程实测后定'),('顶部接口','主控/配件板边距暂定 5.3、插深 2.5；轴向调节 ±0.6')]
for i,(a,b)in enumerate(data):
 y=312-i*29;txt(637,y,a,11,teal);txt(730,y,b,10)
txt(637,105,'射频间距为几何避让目标；读距、天线匹配及握持遮挡仍需整机验证。',10,muted)
C.showPage()

header(4,'PCB 固定重做 · 可核对的安装基准','保留现有板孔；主控采用三个螺丝点 + 一个无帽定位销，电源板四孔独立固定。载荷由骨架与外壳止挡传递。')
def mountplot(name,cx,cy,s):
 b=D['boards'][name];w,h=(40,50)if name=='main'else(38,48)
 def R(x,y):return(cx+x*s,cy+y*s)
 rect(*R(-w/2,0),w*s,h*s,'#D4E5DA',teal)
 for i,(x,y,d)in enumerate(b['holes']):
  locator=name=='main'and i==1
  circle(*R(x,y),2.5*s,None,muted)
  circle(*R(x,y),(.95 if locator else 1.1)*s,amber if locator else white,amber if locator else ink)
  if locator:txt(*R(x-2.7,y-6),'定位销',9,orange)
 if name=='main':
  r=next(q for q in b['components']if q['ref']=='R1');x0,y0,x1,y1=r['court'];rect(*R(x0,y0),(x1-x0)*s,(y1-y0)*s,orange,orange);txt(*R(8,8),'R1',9,orange)
  for c in b['components']:
   if c['ref']=='U1':
    x0,y0,x1,y1=c['body'];rect(*R(x0,y0),(x1-x0)*s,(y1-y0)*s,None,line);txt(*R(0,-5),'模组伸出板边',9,muted,align='center')
 a,bx= (-16,16)if name=='main'else(-15,15);yt=46 if name=='main'else 44
 dim(R(a,yt),R(bx,yt),str(bx-a),offset=32)
 dim(R(bx,4),R(bx,yt),str(yt-4),offset=32)
 txt(cx,cy+h*s+64,'主控板 40×50'if name=='main'else'电源板 38×48',16,align='center')
 txt(cx,cy-58,'孔 Ø2.2；板厚暂按 1.6',11,muted,align='center')
mountplot('main',188,371,4.7);mountplot('power',465,371,4.7)
rect(640,363,522,330,white,line,r=14);txt(664,659,'固定点坐标（从各自 PCB 原点读取）',16)
txt(664,627,'主控：(-16,4)、(+16,4)、(-16,46)、(+16,46)',12)
txt(664,601,'电源：(-15,4)、(+15,4)、(-15,44)、(+15,44)',12)
txt(664,570,'主控 (+16,4) 孔旁的 R1 占用了常规垫圈空间。',12,orange)
txt(664,547,'该孔用 Ø1.9 无帽塑料定位销，底面仍有 Ø5 支撑。',12)
txt(664,524,'定位销与 R1 焊盘包络最近约 0.83；其余 3 孔锁紧。',12)
txt(664,490,'其余固定：M2 尼龙螺丝，Ø4.8×0.5 垫圈，独立托座。',11.5)
txt(664,467,'名义叠厚 0.5 + 1.6 + 3.5 + 1.6 = 7.2，先按 M2×8 配。',11.5)
txt(664,444,'螺丝长度以到货头型 / 螺母为准；托座下方须保留尾端空间。',11,muted)
txt(664,410,'核查结果：拟定支撑 / 螺丝包络与现有器件包络重叠 0 项。',11.5,teal)
txt(664,387,'范围是二维包络及高度预算，未进行实体 CAD、强度或跌落验证。',10.5,muted)
rect(38,60,1124,236,'#F0F4ED',line,r=14)
txt(62,266,'装配方式与下一轮冻结项',17)
note(62,234,'可拆装，不把插针当结构锁扣',['1. 独立装好主控、电源托架及预插线束。','2. 托架固定到骨架；电池绑带固定到托杯。','3. 装屏幕、NFC、触摸电极、扬声器与拨片。','4. 前后半圆壳合拢，上下端圈轴向压住骨架。','5. 配件先由非对称导向键定位，再插电气触点。'])
note(432,234,'目前明确的三类尺寸',['已读 PCB：板框、安装孔、器件 XY 与板面。','设计分配：Ø64/Ø40、板距、壁厚、托座、线槽。','仍待实测：屏幕外形/FPC、电池含保护板尺寸、','连接器插合、线束弯折、按键行程、打印收缩。','主控与配件导向肩承担力；承力尺寸待模型阶段核验。'])
note(815,234,'来源与适用边界',['PCB：V082 保存快照，2026-10-28。','旧 V04 仅借用电池/屏幕/扬声器名义包络。','握柄参考：CCOHS power grip 30–50 mm。','天线参考：Espressif 天线净空设计指南。','本次产物仅二维图纸及计算，不是可打印模型。'])
C.linkURL('https://www.ccohs.ca/oshanswers/ergonomics/handtools/tooldesign.html',(813,140,1140,161),relative=0)
C.linkURL('https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/pcb-layout-design.html',(813,120,1140,141),relative=0)
C.showPage();C.save()
print(O/'器灵_圆筒外壳V05_爆炸图与尺寸核算.pdf')
