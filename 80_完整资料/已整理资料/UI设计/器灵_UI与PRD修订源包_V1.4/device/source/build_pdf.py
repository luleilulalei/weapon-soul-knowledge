from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas
P=Path(__file__).resolve().parent.parent
out=P/'器灵_非触摸圆屏完整状态板.pdf'
c=canvas.Canvas(str(out));c.setTitle('Spirit Display-only Revision - 66 State Mappings')
for p in sorted((P/'boards').glob('*.png')):
 w,h=Image.open(p).size;c.setPageSize((w*.5,h*.5));c.drawImage(str(p),0,0,w*.5,h*.5);c.showPage()
c.save();print(out)
