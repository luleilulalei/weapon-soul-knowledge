# 器灵 App UI V1.4

70个原有/复用状态调整后为71个当前状态。全部横屏844×390，PNG为1688×780。

本版替代旧版中的记忆编辑、闯关保存询问和软件端对话入口。详细变更见screens.md，当前路由见screens.json。

重新生成：node app/src/build.mjs；python app/src/build_manifest.py；node app/src/build_boards.mjs。

图稿与离线模拟不是实机实现。旧版原型不适用于本次边界，使用V1.4原型。
