from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
W,H=1760,1320
im=Image.new('RGB',(W,H),'#f4f6fa');d=ImageDraw.Draw(im)
f='/System/Library/Fonts/STHeiti Medium.ttc'
def font(n):return ImageFont.truetype(f,n)
def txt(x,y,s,n=23,c='#203047'):d.text((x,y),s,font=font(n),fill=c)
colors={'power':'#ffddac','logic':'#bed9fb','analog':'#bce9df','connector':'#d6ccf2','reserve':'#e7e9ee'}
txt(65,35,'器灵 · PCB 布局方案 B · 按连接关系分区',42)
txt(67,94,'重点：降压靠近主控、触摸避开开关电源、提前预留 USB 和供电通道。当前为方案示意。',23,'#56677e')
S=8.3; Y0=205; xs=[125,620]
def xy(i,x,y):return (xs[i]+(x+17)*S,Y0+(141-y)*S)
def rect(i,a,b,c,e,label,kind='logic',size=19):
 x1,y1=xy(i,a,e);x2,y2=xy(i,c,b)
 d.rounded_rectangle((x1,y1,x2,y2),radius=6,fill=colors[kind],outline='#738398',width=2)
 lines=label.split('\n')
 while size>11 and (max(d.textlength(line,font=font(size)) for line in lines)>x2-x1-8 or len(lines)*(size+5)>y2-y1-4):size-=1
 total=len(lines)*(size+5)
 for k,line in enumerate(lines):
  width=d.textlength(line,font=font(size));txt((x1+x2-width)/2,(y1+y2-total)/2+k*(size+5),line,size)
def note(x,y,title,lines):
 txt(x,y,title,27)
 for j,line in enumerate(lines):txt(x,y+43+j*32,line,22,'#53637a')
for i,title in enumerate(['正面 TOP','背面 BOTTOM']):
 txt(xs[i]+37,153,title,29)
 coords=[(-17,141),(17,141),(17,36),(9.8,36),(9.8,42.5),(-9.8,42.5),(-9.8,36),(-17,36)]
 d.polygon([xy(i,*p) for p in coords],fill='#fff',outline='#223d55',width=3)
 # antenna projection intentionally extends beyond notched substrate
 rect(i,-9.8,36,9.8,42.5,'天线净空','reserve',19)
 for yy in range(37,43):
  x,y=xy(i,-9.8,yy);x2,y2=xy(i,9.8,yy);d.line((x,y,x2,y2),fill='#c2c7d0',width=1)
 txt(xs[i]+18,1105,'板外形 34 × 105 mm',23)
 txt(xs[i]+5,1142,'两面均按同一俯视坐标显示',19,'#66758a')
 # dimension ticks
 for yy in [141,125,110,95,80,65,50,36]:
  x,y=xy(i,-17,yy);d.line((x-8,y,x,y),fill='#8795a7',width=2);txt(x-47,y-9,str(yy),16,'#66758a')
rect(0,-8,100,8,135,'屏幕排线通道\n保留高度与弯折空间','reserve',18)
rect(0,-13,67,13,93,'扬声器占用区\n正面不放凸起器件\n核对音腔与走线空间','reserve',21)
rect(0,-9.8,42.5,9.8,64,'主控 U1\nESP32-S3 模组\n去耦紧贴电源脚','logic',22)
rect(0,-7.5,94,7.5,99.5,'音频功放 U4','analog',18)
rect(0,8.7,101,14.5,122,'麦克风\nU5\n及电平\n转换','analog',17)
rect(0,-5,123,5,128.6,'J8\n屏幕接口','connector',17)
rect(0,9,131,17,140.5,'USB-C\nJ101','connector',17)
for y,name in [(130,'J1'),(119,'J6'),(112,'J4'),(104,'J2'),(96.3,'J112')]:rect(0,-16,y-2.5,-9,y+2.5,name,'connector',16)
for y,name in [(127,'J110'),(96.8,'J3')]:rect(0,9,y-2,16,y+2,name,'connector',16)
rect(0,10,44,15.4,63,'去耦\nUSB\n串阻','logic',17)
rect(1,-7.5,132,7.5,140,'充电 U102\n输入保护 / 滤波','power',18)
rect(1,-7.5,122,7.5,131,'电源选择\n硬关断接口 / 跳线','power',18)
rect(1,1,69,14,79,'降压 U103 + L101\n输入输出电容成组','power',17)
rect(1,-5,112,7,121,'升压 U104 + L102\n与触摸区错开','power',17)
rect(1,8.5,122,15.5,130,'振动驱动\nU105','power',16)
rect(1,-15,96, -4,107,'触摸 U3\n输入保护 / 滤波','analog',17)
rect(1,0,96,7.5,104,'扩展 IO\nU7','logic',17)
rect(1,-14,65,-3,72.5,'IMU U2\n隔离振动与电感','analog',16)
rect(1,-15,74,-4,77.5,'光刃转换 U8','logic',15)
rect(1,-13,45,13,62,'启动 / 复位 / 电池采样\n远离开关电源节点','logic',21)
rect(1,-6,81,7,92,'信号 / 测试通道\n为纵向互连留空间','reserve',16)
for a,b,c,e,label in [(-16,78,-9,90,'J7'),(9,84,16,92,'J5'),(9,100,16,106,'J105'),(9,111,16,118,'J104')]:rect(1,a,b,c,e,label,'connector',17)
rect(1,9,132,16,140,'USB ESD\n短直连接','analog',16)
# Arrows mark connectivity corridors, not actual routed tracks.
import math
def route(i,points,color,width=4,dashed=False):
 ps=[xy(i,*p) for p in points]
 for a,b in zip(ps,ps[1:]):
  if dashed:
   length=math.dist(a,b)
   for z in range(0,int(length),16):
    t=z/length;u=min((z+8)/length,1)
    d.line((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u),fill=color,width=width)
  else:d.line((*a,*b),fill=color,width=width)
 a,b=ps[-2:];ang=math.atan2(b[1]-a[1],b[0]-a[0]);d.polygon([b,(b[0]-12*math.cos(ang-.45),b[1]-12*math.sin(ang-.45)),(b[0]-12*math.cos(ang+.45),b[1]-12*math.sin(ang+.45))],fill=color)
route(0,[(16,131),(16,59),(14.5,59)],'#1673cc',3)
route(0,[(16.5,131),(16.5,59.6),(14.5,59.6)],'#1673cc',2)
route(1,[(-7.8,126),(-8.3,123),(-8.3,110),(-1.5,110),(-1.5,77),(1,77)],'#cb7620',4,True)
route(1,[(7,69),(7,64)],'#c55319',5)
route(1,[(-16,104),(-13,104)],'#129889',4)
route(1,[(0,112),(0,108),(8,108),(8,93),(8,80),(-8,80),(-10,82)],'#a87333',3,True)
note(1030,180,'01  降压下移，缩短主控供电',[
 'U103 / L101 移至主控上方背面。',
 '让稳压输出短接主控去耦，避免长距离供电。',
 '代价：上游 MAIN_IN 变长，需核算压降与回流。'])
note(1030,350,'02  触摸靠左，升压移向中央',[
 'U3 靠近正面 J2，六路输入优先短直连接。',
 '升压位于更上方，电感与 SW 铜皮限制在小区内。',
 '5V 干线绕开触摸输入，不能穿过触摸器件组。'])
note(1030,520,'03  先留通道，再摆外围器件',[
 '蓝色双线：USB 专用走廊，ESD 紧贴连接器。',
 '橙色虚线：MAIN_IN 至降压的内层供电意向。',
 '棕色虚线：5V 至光刃接口；绿色：触摸输入。'])
note(1030,690,'04  配合四层板安排回流',[
 '优先保持内层 1 的 GND 参考连续。',
 '内层 2 可承担电源分配，具体铜宽按电流核算。',
 'USB 的层叠、阻抗、换层与回流要单独验证。'])
note(1030,860,'05  这版仍要过实际封装检查',[
 '色块和箭头不是封装落位，也不是已完成走线。',
 '需验证电池高度、声道、插头出线与器件间距。',
 '若空间不足，先调整分区，不靠缩小间距硬塞。'])
for j,(name,k) in enumerate([('电源 / 驱动','power'),('数字 / 主控','logic'),('模拟 / 传感','analog'),('连接器','connector'),('保留空间','reserve')]):
 x=65+j*320;d.rounded_rectangle((x,1200,x+28,1228),radius=4,fill=colors[k],outline='#738398');txt(x+40,1199,name,22)
txt(65,1270,'状态：功能分区提案，未写入 PCB，未进行自动布线；器件间距和机械适配需在下一阶段验证。',22,'#56677e')
p=Path('output/layout/spirit-functional-zones-B.png');im.save(p)
print(p.resolve())
