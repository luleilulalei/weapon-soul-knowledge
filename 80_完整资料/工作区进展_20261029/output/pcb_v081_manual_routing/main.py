from engine import *
b=Board('main');cn=b.cn;tr=b.tr;via=b.via;esc=b.esc;p=b.pt
for module in ['nfc','display','audio','microphone','backlight','touch','sensors_i2c','haptic','usb','controls','reset_uart','accessory','main_power','main_ground','main_finish']:
 exec((Path(__file__).resolve().parent/(module+'.py')).read_text())
if __name__=='__main__':b.save()
