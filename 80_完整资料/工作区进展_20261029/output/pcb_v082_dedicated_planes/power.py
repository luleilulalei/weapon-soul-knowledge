from engine import *
b=Board('power');cn=b.cn;tr=b.tr;via=b.via;esc=b.esc;p=b.pt
for module in ['power_converters','power_charge','power_controls','power_typec','power_usb','power_interconnect','power_rails']:
 exec((Path(__file__).resolve().parent/(module+'.py')).read_text())
if __name__=='__main__':b.save()
