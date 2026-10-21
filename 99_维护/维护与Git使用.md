# 维护与Git使用

本仓库是器灵的可携带项目记录。Git保存修改历史，不会自动把内容写入聊天记忆，也不会自动同步另一台电脑。

## 日常更新

1. 阅读MEMORY.md与当前基线，定位对应主题。
2. 新结论记录来源和日期，区分用户决定、提案、工程实现与实测。
3. 如果替代旧要求，更新决策台账和历史替代关系；保留原始证据。
4. 保存新增证据快照、完整原件及SHA-256，更新来源清单。原件目录内部关系保持完整；旧证据不覆盖，更新中的原件同时保存变更前版本。
5. 更新MEMORY.md和更新记录，运行校验，再检查差异并提交。

## 常用命令

在仓库目录执行：

```sh
git status --short
git diff
python3 tools/verify.py
git add -- 明确修改的文件
python3 tools/verify.py --check-git
git commit -m 'docs: 说明本次决定或进展'
git push
git log --oneline -8
```

`git add`一行中的“明确修改的文件”需替换为实际路径。本次用户明确要求完整保存原件，因此已有工程、模型、构建包和安装包直接入库。Unity 等原包自带的嵌套忽略文件可能忽略构建产物，完整归档时需对已确认的原件使用 `git add -f -- 80_完整资料`，再运行 `--check-git` 确认没有漏项。后续更新仍只加入器灵项目相关内容。

需要检查原目录是否已变化时使用 `python3 tools/verify.py --check-originals`。它会核对已收录原件，并枚举指定目录寻找新增漏项；证据或归档字节不一致会失败。历史版本与当前原件分别核对。新电脑缺少原绝对路径时会报告来源不可用，仓库内完整资料仍可使用。

## 跨电脑和云端接续

远程仓库为 [luleilulalei/weapon-soul-knowledge](https://github.com/luleilulalei/weapon-soul-knowledge)，SSH 地址：`git@github.com:luleilulalei/weapon-soul-knowledge.git`。主分支为 `main`，未设置自动同步任务。

997 个归档原文件由普通 Git 保存，约 173 MB 的 `UnityPlayer.dylib` 由 Git LFS 保存。GitHub 普通文件限制为100MiB，因此初次推送前将这一文件迁移到LFS，改写了尚未发布的本地提交编号；迁移前完整历史备份和提交对应关系保留在本次项目工作目录的 `knowledge_push/before-lfs.bundle`、`knowledge_push/lfs-commit-map.csv`，未作为远程分支推送。

另一台电脑先安装 Git 和 [Git LFS](https://git-lfs.com/)，配置有权访问该仓库的 GitHub 账号，然后执行：

```sh
git lfs install
git clone git@github.com:luleilulalei/weapon-soul-knowledge.git
cd weapon-soul-knowledge
git lfs pull
python3 tools/verify.py --check-git
```

普通 GitHub ZIP 下载不作为完整工程备份验收依据；以上校验会确认LFS原文件已下载、大小与SHA-256匹配。归档标签 `kb-2026-10-21`、`kb-2026-10-21-full` 保留对应历史版本；完整版标签已随LFS迁移更新。

在新聊天中明确提供本仓库目录，先读MEMORY.md、当前基线和相关主题。只使用云端聊天时，可提供MEMORY.md及需要的主题文档；如果上传静态副本，应带更新日期，更新后重新同步。保存文件本身不保证任何聊天会自动读取。

## 证据维护

`90_来源/文档快照/`保留旧文档原字节。原文的相对图片或附件链接可能指向原始包，不要求在证据目录内重写。`80_完整资料/`保留完整原包目录关系；不因修复旧文档链接而修改原件。

校验工具检查当前整理文档和图册链接、证据与原件SHA-256、Word/PDF提取覆盖、原型内嵌图出处、普通Git原件字节，以及LFS指针和下载后的大文件原字节。大型文件只对白名单清单中的原件放行。它不验证电子电路、产品运行或历史测试结论。

`99_维护/校验报告.json`保存归档检查结果。一个原有空目录名称记录在完整收录清单中；Git不保存空目录，必要时按记录重建即可。
