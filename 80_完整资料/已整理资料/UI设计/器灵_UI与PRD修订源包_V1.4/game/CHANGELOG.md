# 游戏 UI v1.4 变更

## 本轮修改

1. G17 首次通关、G17R 重复通关、G22 守门者胜利：移除结算后的记忆决定和共同经历入口及点击热区。成绩、一次解锁、继续、再练、休息保留；底部改为不可点击的安全提示。
2. G02B 充电受阻：按钮改为“返回器灵主页”，只指向器灵/设备状态。充电禁练与安全准备不变。
3. G23 主动退出：删除关于共同经历的保存结果陈述，只显示已有技能与本局技能结果。
4. HUD 的麦克风文案明确为硬件只读状态。游戏没有对话、语音录入或聊天入口；固定叙事与动作教学保留。
5. screens.json、context.json、manifest.json、规格、源代码、SVG、PNG 和四张评审板同步。未新增闯关记忆自动保存规则。

## 文件与复现

- 58 个横屏状态，44 张 SVG 有变化，58 张 PNG 已重新渲染。
- 四张 SVG/PNG 评审板已同步。
- source/ 和 assets/ 包含独立重建所需输入；运行 python build_landscape.py，再运行 node render.js。
- qa/change_inventory.json：逐项变更和不变项。
- qa/extension_audit.json：14 张扩展教学状态审计。
- qa/visual_review.md 与 validation.json：视觉检查与自动检查结果。
- 原版本目录未修改。
