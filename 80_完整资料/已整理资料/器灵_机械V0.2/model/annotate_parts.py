from PIL import Image,ImageDraw,ImageFont
import json,os
M=os.path.dirname(os.path.abspath(__file__));R=os.path.dirname(M);im=Image.open(R+'/renders/07_print_parts_unlabelled.png').convert('RGB');out=Image.new('RGB',(1800,1520),(42,44,45));out.paste(im,(0,90));d=ImageDraw.Draw(out);F='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc';F=F if os.path.exists(F) else 'DejaVuSans.ttf';font=lambda z:ImageFont.truetype(F,z)
d.text((35,14),'12个独立STL  /  9个结构件 + 3个试片',font=font(34),fill=(239,235,218));d.text((35,60),'同一比例，毫米；各1件。先P08，再P09/P10，实物试配后打印整壳。摆盘仅作展示。',font=font(22),fill=(180,201,204))
for r in json.load(open(M+'/part_layout_labels.json')):
 x,y=r['xy'];d.text((x,y+90),r['id'],anchor='mm',font=font(24),fill=(235,205,140))
d.text((35,1470),'打印方向按STL提供；切片时仍须检查支撑、孔径、薄壁、平台尺寸和局部悬空。电子假件不在STL中。',font=font(23),fill=(220,188,140));out.save(R+'/renders/07_print_parts.png')
