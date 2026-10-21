from PIL import Image,ImageDraw,ImageFont
import os,json
R=os.path.dirname(os.path.abspath(__file__));O=os.path.dirname(R);F='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
if not os.path.exists(F): F='DejaVuSans.ttf'
font=lambda n:ImageFont.truetype(F,n)
for src,coords,out,title in [('03_open_back_cutaway.png','callouts.json','05_annotated_internal_layout.png','器灵 V0.2  /  内部位置与选定器件'),('02_exploded.png','callouts_exploded.json','06_annotated_exploded.png','器灵 V0.2  /  可拆结构与装配层次')]:
 im=Image.open(O+'/renders/'+src).convert('RGB'); canvas=Image.new('RGB',(1740,1540),(42,44,45));canvas.paste(im,(0,100));d=ImageDraw.Draw(canvas)
 d.text((45,20),title,font=font(38),fill=(237,233,219));d.text((45,72),'实际 Blender 几何  ·  FPC裸屏 + 18650 + LRA  ·  实物装配待验证',font=font(21),fill=(170,191,194))
 data=json.load(open(R+'/'+coords))
 for i,r in enumerate(data):
  x,y=r['xy'];y+=100;ly=160+i*(125 if len(data)>7 else 155)
  # Endpoint on part is a locator; rear-view concealed features remain explicitly called positions.
  d.line([(x,y),(1110,ly+18),(1140,ly+18)],fill=(107,153,164),width=2)
  label=r['n'];w=d.textbbox((0,0),label,font=font(21))[2]+20
  d.rounded_rectangle((x-w/2,y-18,x+w/2,y+18),8,fill=(218,231,230),outline=(38,93,102),width=2);d.text((x-w/2+10,y-16),label,font=font(21),fill=(24,60,68))
  d.text((1150,ly),label+'  '+r['label'],font=font(24),fill=(237,233,219))
  d.text((1150,ly+42),('后盖、托架及LRA支架隐藏' if src.startswith('03') else '编号对应打印零件清单'),font=font(17),fill=(165,179,180))
 d.text((40,1500),'尺寸、紧固件与零件标号见机械装配与试打印说明；部分前侧器件被遮挡；RF、排线、声学及实物适配仍须验证。',font=font(22),fill=(221,185,133))
 canvas.save(O+'/renders/'+out)
