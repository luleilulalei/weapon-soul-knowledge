# 器灵 单IMU功能原型 v0.1 · Unity源码交付

## 交付状态（2026-10-17）
这是实际C#实现，不是静态PRD：无Unity插件依赖，包含纯C#规则、候选识别器、CSV解析、Unity横屏界面及自测。当前交付环境未安装Unity、dotnet、csc、mcs或mono，所以**没有执行C#编译、Unity Play Mode、Android构建或实体传感器实测**。独立Python参考回放报告只验证参考逻辑/数据，不能替代C#执行。不得以此包宣称硬件识别率、延迟、Android适配或发布验收通过。

## 最少运行步骤

**仅导入新建的空白Unity测试项目。不要直接导入现有正式App。** 此包会在运行时自动Bootstrap界面，菜单会调整演示场景/横屏设置（保留原Build Settings其他场景）。功能验证界面不替代用户已经认可的高保真UI。合并正式App前需移除自动Bootstrap并接入已有导航/输入生命周期。
1. 用已安装的Unity 2022.3 LTS或Unity 6创建空白3D项目（版本兼容仍待实编译确认）。
2. 将本目录下整个Assets/SpiritIMU复制到项目Assets内。不需要下载包，不需要创建Canvas、素材、预制体或挂脚本。
3. 打开任意空场景，点击Play，程序自动生成横屏界面；也可菜单Spirit IMU → Create demo scene，生成并保存演示场景并加入Build Settings。
4. 勾选空间安全确认。点“1. Simulated preparation”，选择Tutorial/Rhythm/Boss和反击方式，再点“2. Start NEW attempt”。模拟准备明确不代表真实校准。
5. 触屏/鼠标按钮即可操作。旧输入管理器启用时支持A左斩、D右斩、S下劈、G格挡、C朝上持势800ms、X取消、Space暂停。新Input System专用项目仍可用屏幕按钮，无Input System包依赖。
6. 菜单Spirit IMU → Run core self tests运行纯C#自测；只有实际运行通过，Console才会输出passed。这里没有预先宣称通过。
7. Android：本地Unity需已安装Android Build Support与SDK/NDK；生成场景后Build Settings/Build Profiles切Android，自行选择签名/包名并构建。源码设LandscapeLeft且界面按1280×720缩放，尚未验证刘海、安全区、真实设备字体/性能。没有随包APK。

界面暂用英文以避免空项目缺少CJK字体造成不可见标签；功能说明为中文。金青深色、横屏功能样式，不是最终美术或正式全App实现。

## 已实现玩法
- 五段教学：左斩、右斩、持势格挡、朝上蓄力（Start后≥800ms才Ready）、取消/归位。下劈在Boss蓄势反击里演示。
- 节拍挑战：左→右共4组；≥3完整组为当次模拟通过。错斩失败当前组；超时结束当前组，不继承到下一组。没有永久解锁/成长。
- Boss四阶段互斥：防御1000ms→预告1200ms→攻击窗口1200ms→格挡成功进入反击3500ms。未格挡失1格，双方3格。当前选定的基础斩、左→右组合、朝上持势→下劈三轨道互斥。
- 所有数字是未实测的工程演示参数。实际难度、动作准确率、舒适姿态和时延须样机数据修订。
- 暂停立即冻结且清除蓄力/组合，明确要求重新准备和新开一局；本原型没有从旧窗口恢复的功能。暂停不写胜负/奖励。
- 断连、后台/失焦、帧间隔>250ms、输入失效、充电、入座中断；条件恢复不会接续旧局。终态不被晚到输入改写；此前正常终态保留。此处是本地串行已知顺序，不实现跨设备顺序未知的待核对账本。
- Cancel控件始终可取消蓄力，包括原始输入模式；在事件中明确标为simulated控制，不假称IMU识别。原始IMU自动识别“取消/归位”尚未实现。

## CSV回放与录制
Resources/sample_raw.csv是**人工合成**30秒100Hz夹具，没有实体采集数据。列必须严格为：
`sessionId,deviceId,seq,tMs,ax,ay,az,gx,gy,gz,source`

单位：accel g、gyro deg/s；seq与tMs严格单调递增；tMs为毫秒。每文件只能一个sessionId/deviceId，source枚举simulated/replay/hardware。无标题别名/Excel地区逗号/引号字段兼容承诺；标识符不要包含逗号或换行。

点击Load bundled raw CSV开始按原始时间差播放，前1秒静止用于校准；校准完成后确认方向映射（Directions manually verified）再点Start。回放不会自动开战。夹具的动作节奏不保证恰好匹配手动开局后的游戏窗口，目的为识别与门禁调试，不是作弊自动通关脚本。换自己的文件时替换该TextAsset并重新导入。时间戳映射到宿主单调时钟，但保留样本间隔；回放源明确标replay。文件终止会中断未完成局。

只有点击Record raw CSV才记录输入样本；再次点击Stop + save（或切换输入源时自动结束本次显式录制）保存到Application.persistentDataPath，状态栏显示路径。无默认自动录制、上传或长期成长。录制存储的是宿主映射后的时间戳，不声称保留设备原始时钟；原始CSV文件可另行保留作溯源。样本缓冲当前在内存，适用于短测，不适合长时间录制。

## 真实IMU接入接口（未实现BLE/固件）
IImuInput事件Sample提供RawSample，Interrupted提供原因，Start/Stop控制适配器。实例化适配器后通过SpiritPrototype.AttachInput传入；所有回调必须调度至Unity主线程。适配器负责：
- BLE或有线传输、设备身份、包解析、CRC/序号、重连、时钟同步与设备轴→剑体轴转换。
- 安全通知优先于同批样本派发；充电/入座/断连调用Interrupted，并通过SpiritPrototype.UpdateDeviceState(connected, charging, docked, reason)同步门禁状态；状态改变会要求新准备。本示例按钮只模拟这些状态。
- 映射到宿主Time.realtimeSinceStartupAsDouble毫秒，不能把不同设备启动时间直接当宿主时钟。
- 换设备、重启或重连必须重置输入适配与重新校准，不沿用旧session/seq。

依据恢复的接口资料（仅文档核对）：BMI270 0x69，GPIO41 SCL、GPIO42 SDA、GPIO38 INT1、3.3V/400kHz，CSB/SDO拉高、INT2 DNC。此源码不配置引脚，不含硬件驱动，不代表原理图制造放行。

## 候选识别边界
CandidateRecognizer只是显式实验候选模块；没有训练模型、四元数融合、空间坐标、位移积分或剑尖轨迹。BMI270只有加速度/角速度；重力无法提供面向手机的绝对yaw。
- 接口剑体轴：+Y指向剑尖，+X在中性时指玩家右方，+Z指玩家；必须经实际装配映射验证。面向屏幕与左右/下劈方向需人工示范核验；界面提供左右手、水平符号/下劈符号翻转，改变后重新准备。HorizontalSign明确是右手基准符号，再由LeftHanded镜像；若按当前手别演示调整符号，必须避免再额外镜像，最终以本手别的左右示范核验为准。
- 静止1秒且至少20点、|accel模长−1g|<0.12、gyro模长<12deg/s后只估计陀螺零偏；不是绝对朝向校准。
- 候选斩击：主轴角速度>120deg/s，较另外两轴至少1.4倍；300ms冷却，回到低速才重新武装，避免一段持续旋转多次触发。此简化轴阈值不是可靠动作分类验收。
- 静止条件下ay/|a|>0.85表示剑轴朝上；不推断手臂或头顶高度。格挡候选为剑轴接近水平（|ay/|a||<0.3）且静止保持250ms才GuardEnter，无法判断水平面偏航或物理碰撞；蓄力窗口保持800ms才ChargeReady，两窗口互斥。
- 错方向斩击、取消/归位或离持势清蓄力；已就绪下劈单次消耗。不把格挡判定解释成物理接触。
- 重复/乱序/非有限数样本丢弃且不刷新有效输入新鲜度；间隔>250ms需重校准。动作事件session/window/ID、[open,close)边界和250ms时效分别核验。设备失效不能靠回放自动变成在线有效成绩。

## 测试文件与尚未覆盖
Core/CoreSelfTest.cs：无NUnit依赖，包含安全开局、4组、去重、窗口上界、过期、暂停/重开、格挡/三段蓄力、错误斩击取消、充电/入座、候选校准、持续挥动、CSV NaN等断言。源码交付时未在C#运行时执行。
总包validation目录包含独立审核/参考回放。请分别记录：参考实现实际运行、C#核心编译+执行、Unity场景运行、Android构建/装机、实体识别/安全/延迟，不能互相替代。

未实现：BLE、固件、灯/声/震实物驱动、AI/语音、账号、真实奖励/成长、正式解锁政策、联网结算/待核对恢复、App完整导航、可靠自动朝向识别、完整动作数据集与识别率。原型无网络调用和支付能力。

原始蓄力释放：已Ready后离开朝上姿态进入300ms release-pending候选，不继续蓄力；窗口内下劈可释放，错误横斩/反向角速度/超时/重返朝上/取消/暂停/断连取消，Ready之前离姿立即取消。300ms是未实测提案；此状态链修复不代表自然挥动识别准确率验证。

独立C#命令入口：如开发机器已有.NET 8 SDK，可在本目录运行 `dotnet run --project Tests/RunCoreTests.csproj`，不需要Unity来测试纯Core。该命令在本交付环境未执行；项目无第三方NuGet依赖。
