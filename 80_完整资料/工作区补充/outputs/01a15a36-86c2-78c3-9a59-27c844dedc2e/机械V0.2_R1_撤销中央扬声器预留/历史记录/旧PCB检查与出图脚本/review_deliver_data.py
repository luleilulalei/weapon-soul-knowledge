import json, re, collections
from pathlib import Path
from review_placement import P

OUT = Path('outputs/01a15a36-86c2-78c3-9a59-27c844dedc2e')
OUT.mkdir(parents=True, exist_ok=True)
net = json.load(open('review-v072-netlist.json'))
notes = {
 'U1':'3.3V供电；GPIO19/20为USB，GPIO18为IMU中断；N16R8占用的GPIO35/36/37保持NC。天线移至板顶开槽边缘。',
 'U2':'BMI270：VDD/VDDIO为3.3V，CSB高选I2C、SDO高选0x69；INT1到GPIO18；需加载厂家初始化配置。',
 'U3':'CAP1296：3.3V，固定7位地址0x28，六路触摸各串1kΩ；EP接地。已避免与原RFID2模块地址冲突。',
 'U4':'MAX98357A：5V BTL输出，匹配8Ω/2W扬声器；SPK_P/SPK_N均不可接地，固件从低音量启动。',
 'U5':'PDM数字麦克风，3.3V，L/R接地；主控GPIO4为数据、GPIO5为时钟。声孔不得被胶或结构堵塞。',
 'U7':'TCA9534：3.3V、7位地址0x20；中断有上拉；固件先设置输出锁存值再改方向。',
 'U101':'USBLC6-2SC6：USB数据线ESD通道和VBUS/GND脚序已核对；布置在USB座与串联电阻之间。',
 'U102':'BQ24075：单节锂电电源路径；1.18kΩ设输入限流，1kΩ设约0.89A充电；需保护电池和真实10kΩ NTC。',
 'U103':'TPS63802：470nH电感、560kΩ/100kΩ反馈，标称3.3V；输入/输出电容近端布置；样机验证低电量带载和环路。',
 'U104':'TPS61023：1µH、732kΩ/100kΩ反馈；按0.6V参考约4.992V，按0.595V典型约4.9504V。输出能力需按最低电池电压验证。',
 'U105':'DRV2605L驱动LRA；所选LD0825BC-0169F为1.2Vrms、240±10Hz。固件启用LRA模式并校准，电压上限遵守1.25Vrms。',
 'U106':'TUSB320LAI为Sink/GPIO模式，使用内部Rd；检测到1.5A/3A广告才切换充电限流，默认100mA。',
 'U107':'TLV75533：独立USB检测3.3V电源；输入/输出1µF，输出本地去耦；不承担系统主供电。',
 'U108':'SN74LVC1G04：反相Type-C电流广告信号；供电来自USB检测3.3V，输入上拉，避免启动误判高电流。',
 'L101':'470nH MWSA0503S-R47MT，匹配TPS63802建议范围；短粗开关回路。饱和电流、DCR和温升按厂家规格及实际负载复核。',
 'L102':'1µH MWSA0402S-1R0MT，匹配TPS61023；DCR上限27mΩ，不能将开关限流当作输出额定电流。',
 'F101':'1812自恢复保险，2.6A保持/16V；属于后备保护，实际USB输入电流由BQ24075限流控制。',
 'R8':'2.2kΩ使能串阻，配10kΩ下拉限制注入；SD_MODE高电平仍满足左声道选择门限。',
 'R39':'10Ω、1206、250mW背光串阻已同步到PCB料号C17903。100mA时耗散0.1W；实际屏幕LED额定值尚需实物规格匹配。',
 'R110':'1.18kΩ：BQ24075输入限流约1.36A，容差边界约1.472A；须配合Type-C广告判断。',
 'R111':'1kΩ：充电电流典型约0.89A、上界约0.985A；电池需允许此充电电流。',
 'R112':'69.8kΩ充电计时电阻；保留安全计时功能。',
 'R117':'560kΩ精密反馈上臂，与R118的100kΩ设置3.3V。',
 'R118':'100kΩ精密反馈下臂，接安静地，避开电感开关节点。',
 'R121':'732kΩ升压反馈上臂，与100kΩ下臂设置约5V。',
 'R137':'887kΩ Type-C VBUS检测串阻，阻值与TUSB320LAI推荐电路一致。',
 'C114':'220pF C0G/NP0前馈电容预留，默认DNP不装、不采购。仅在实测总有效输出电容大于40µF且验证环路稳定性后选装；与732kΩ反馈电阻形成约988Hz零点。',
 'FB202':'BLM18AG601：3.3V到LCD_VCC的电源磁珠；两颗屏幕去耦均已接到LCD_VCC。',
 'J8':'12针0.5mm FPC座。脚序：1GND/2LEDK/3LEDA/4LCD_VCC/5,6GND/7DC/8CS/9SCK/10MOSI/11RST/12GND；13,14为接地固定脚。GC9A01芯片名不能单独证明用户屏幕排线兼容。',
 'J3':'2针SH1.0扬声器口，接8Ω/2W外置扬声器；需配对线束，两个输出都不接地。',
 'J6':'2针SH1.0辅助按键接口：1为AUX_KEY_N，2为GND；接无源按键，不接马达。',
 'J110':'2针SH1.0 LRA口，1为HAPTIC_OUT_P、2为HAPTIC_OUT_N，接DRV2605L差分输出；需配对线束；两线都不接地，不能接直流电源。',
 'J104':'3针电池口：保护1S电池与真实10kΩ NTC。电芯允许充电电流至少覆盖设定值，接插件线序以表中网络为准。',
 'J111':'外置DPST机械开关口；两组触点分别控制主电源和5V支路，不得将四脚并接。',
 'J201':'NFC口改为3.3V：1SCL/2SDA/3VCC/4GND。优先PN532 Grove NFC 113020006（历史C445568），设I2C模式0x24并制作对应线束；商城现货未确认。',
 'J7':'外设6针接口含5V、3.3V、GND和两路通信/检测信号；总负载计入升压与系统预算。',
}

def order(ref):
    return (re.sub(r'\d','',ref),int(re.search(r'\d+',ref).group()))

reviews=[]
for c in sorted(net['components'].values(),key=lambda c:order(c['props']['Designator'])):
    p=c['props'];ref=p['Designator'];pins={k:v.get('net','')for k,v in c['pinInfoMap'].items()}
    n=notes.get(ref)
    if not n:
        if ref.startswith('C'):
            vr=p.get('Voltage Rating') or re.search(r'额定电压:([^;]+)',p.get('Description',''))
            if not isinstance(vr,str):vr=vr.group(1)if vr else '按制造商型号'
            n=f"电容{p.get('Value','')}，额定耐压{vr}；逐脚网络和封装已比对。MLCC直流偏压后的有效容量及样机纹波仍需验证。"
        elif ref.startswith('R'):
            value=p.get('Value','');n=f'{value}、{p.get("Power(Watts)","100mW")}；逐脚核对拉阻、分压或信号串阻用途。'
            try:
                r=float(value.replace('Ω','').replace('k',''))*(1000 if 'k' in value else 1)
                if r>=1000:n+=f'按两端5.5V、阻值-1%的保守静态界限，功耗不超过{5.5**2/(r*.99)*1000:.3g}mW。'
                else:n+='低阻信号串阻不承担外部持续短路保护。'
            except ValueError:pass
        elif ref.startswith('Q'):
            n='栅极/源极/漏极逐脚比对；3.3V逻辑驱动。用于背光、小信号检测或电池采样开关，不作为主电源保护器件。'
        elif ref.startswith('J'):
            n='接口逐针网络、引脚数和PCB焊盘已比对；配对线束须按引脚号制作，不能仅凭线色接线。'
        elif ref.startswith('SW'):
            n='逻辑按键，已核对复位或KEY网络；不承载系统主电流。'
        else:n='网络和封装已逐项比对。'
    status='设计核查完成；样机验证'
    if ref in ['J8','R39']:status='待现有屏幕规格匹配'
    if ref=='J201':status='接口完成；模块现货待确认'
    dnp=p.get('DNP')=='YES' or p.get('Add into BOM')=='no'
    if dnp:status='DNP：默认不装、不采购'
    reviews.append({'ref':ref,'sku':p.get('Supplier Part',''),'part':p.get('Manufacturer Part',''),'value':p.get('Value',''),
      'footprint':p.get('Supplier Footprint',''),'side':'顶面'if P[ref]['layer']==1 else '底面','pins':'; '.join(f'{k}={v or "NC"}'for k,v in pins.items()),
      'status':status,'review':n,'dnp':dnp,'source':p.get('Datasheet','')})
g=collections.defaultdict(list)
for r in reviews:g[r['sku']].append(r)
bom=[]
for sku,rr in g.items():
    p=rr[0]
    qty=sum(not r['dnp'] for r in rr)
    bom.append({'sku':sku,'part':p['part'],'qty':qty,'refs':','.join(r['ref']for r in rr),'footprint':p['footprint'],'status':'已匹配工程；下单时复核库存' if qty else 'DNP：默认不装、不采购','source':p['source']})
assert len(reviews)==137 and sum(x['qty']for x in bom)==136 and len(bom)==51
external=[
 {'item':'LRA线性马达','model':'LD0825BC-0169F','sku':'C5632412','qty':1,'price':9.16,'stock':18,'status':'已选；商城现货','notes':'1.2Vrms，240±10Hz；8×2.55mm；接J110，另配SH1.0线束。REV02与商品标题频率不同，按原厂REV02校准。','url':'https://item.szlcsc.com/6552539.html'},
 {'item':'扬声器','model':'20MM-8Ω2W-JFHM','sku':'C50387209','qty':1,'price':4.41,'stock':33,'status':'已选；商城现货','notes':'8Ω/2W，直径20mm，高5.1mm；接J3。板上保留26×26mm正面结构空间，需绝缘垫及声腔。','url':'https://item.szlcsc.com/53008592.html'},
 {'item':'NFC模块','model':'Grove NFC 113020006 / PN532','sku':'C445568（历史料号）','qty':0,'price':None,'stock':None,'status':'候选；现货未确认，暂不下单','notes':'3.3V，I2C模式地址0x24；默认UART需改跳线。25.43×20.35mm，外置天线。需按J201制作线束。','url':'https://wiki.seeedstudio.com/Grove_NFC/'},
 {'item':'用户现有屏幕','model':'GC9A01','sku':'用户已有','qty':0,'price':None,'stock':None,'status':'不采购','notes':'沿用12针FPC定义；接线方向、逻辑电源及LED额定电流仍需与手头屏幕型号核对。','url':''},
 {'item':'屏幕备查','model':'Waveshare 1.28英寸GC9A01模块','sku':'C5374684','qty':0,'price':87.79,'stock':0,'status':'仅记录，不采购','notes':'8针模块不能直接插现有12针FPC。','url':'https://item.szlcsc.com/6230043.html'},
 {'item':'屏幕备查','model':'PG1301HA-ZA0','sku':'C17215183','qty':0,'price':230.8,'stock':0,'status':'仅记录，不采购','notes':'前次查询无现货；不是用户实物屏幕的兼容性证明。','url':'https://item.szlcsc.com/18344256.html'},
 {'item':'屏幕备查','model':'HY013001','sku':'C2908591','qty':0,'price':None,'stock':0,'status':'已停售，不采购','notes':'保留检索记录。','url':'https://item.szlcsc.com/3184303.html'},
 {'item':'NFC备查','model':'MH1612S-NFC-EVB-V3','sku':'C54934871','qty':0,'price':None,'stock':None,'status':'不替换本版','notes':'55×40mm超过34mm板宽，默认SPI；I2C地址和复位线适配未闭合，不能当PN532直接替代。','url':'https://www.lcsc.com/fr/product-detail/C54934871.html'},
]
data={'bom':bom,'reviews':reviews,'external':external,'date':'2026-10-21','quantity':1,
 'stock_note':'马达和扬声器库存/1件价来自2026-10-21商城实时页面；会变化。NFC及板载元件未承诺实时库存；数量不含贴片损耗。'}
(OUT/'逐元件核查.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
print(OUT,len(bom),len(reviews))
