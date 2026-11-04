# 092 主仓库远程地址迁移至 wulincong

- 状态：已实现（2026-11-03，SSH 读写、分支与标签同步、前端构建、新远端全新递归克隆、21 文件一致性与区域资源校验全部通过）。
- 动机：主仓库现为 `git@github.com:wulincong/skill-plaza-foru.git`，本机 `origin` 和用户可复制的安装入口仍指向旧所有者；需要衔接现有历史并保留运行环境。

## 约定与接入点

- 本机 `remote.origin.url` 改为新 SSH 地址，继续复用 `origin` 和各分支既有 tracking 配置；`wlc` 仍跟踪 `origin/wlc`。不重建工作目录、不重写历史、不强制推送。操作说明见 `README.md:26`。
- 迁移前读取新远端的 heads/tags，再 fetch 比较历史。本次新远端 `wlc` 为 `a6bb2ae`，本地为 `ea983f2`，`git rev-list --left-right --count origin/wlc...HEAD` 为 `0 18`；这 18 个已有提交已正常快进推送到新远端。迁移文档与链接变更另外提交、打标签，并使用非强制推送同步；现有 37 个本地标签均可从当前分支到达，需一并保留。
- GitHub 默认分支经 `git ls-remote --symref … HEAD` 实测仍为 `codex/foru-demo`；`git remote set-head origin -a` 仅更新本地符号引用，不能修改 GitHub 默认分支。新环境克隆当前版本显式传 `--branch wlc --recurse-submodules`，见 `README.md:39` 与 `web/src/pages/GuidePage.vue:43`。
- 主仓库主页/安装文案统一新地址并显式指定当前 `wlc` 分支：`web/src/components/HeroSection.vue:107`、`web/src/pages/GuidePage.vue:8`、`web/src/data/skills.ts:133`（tech-forecast）及 `:169`（doc-translate），内置技能说明为 `.agents/skills/tech-forecast/README.md:3`。
- `.gitmodules:1` 的 industry-education-report、foru-web-ui、career-guidance 三个独立技能仓库仍属于 `Lntanohuang`，不随主仓库所有者字符串批量替换。它们的 README 中旧主仓库引用属于各子仓库内容，本次不修改其文件或固定提交。
- `chart-visualization` 原固定提交为 `75e10d00fbbcbc7c60cf50e678385afbfe434eb8`，来源 `https://github.com/Lntanohuang/chart-visualization-skill.git`，包含本地 `dfcdafa`（雷达/桑基图规范）、`75e10d0`（桑基图配色规范）两次提交，远端默认 `main` 为另一条历史上的 `776144b`。不能把指针直接改成远端 main，否则会丢失现有图表规范。用户明确选择“改为主仓库内置目录，保留全部现有文件”。
- 内置操作仅移除根索引中的 `160000` gitlink、`.gitmodules` 中 chart 条目、本机该子模块配置和工作目录里的 `.git` 指针文件，再将原目录的全部 21 个文件作为普通文件纳入主仓库。没有执行会清空目录的 `git submodule deinit`，没有覆盖或重新下载技能文件；原子仓库 Git 对象仍留在本机 `.git/modules` 中。既有路径 `.agents/skills/chart-visualization/`、Pi 加载/报告引用路径、地图与规范均保持一致；不增加前端卡片或运行时服务。
- `.github/workflows/close-task-issue.yml:18` 使用 `${{ github.repository }}` 动态定位仓库，迁移无需硬编码新 owner。当前机器未安装 `gh`、未启用 `core.hooksPath`，本次也未启用 Issue hooks；003/005 中 Issue 创建及 Actions 关闭的待验证状态不因 Git SSH 可用而改变。本次新增推送的提交不含 `Task-Issue` trailer。
- 地址迁移仅调整代码来源和远端分支。已有 `web/.env`、本地会话/运行记录/交付存储及依赖目录继续留在本机，线上服务无需因 Git 地址变更而重启；如果另换服务器，这些 gitignored 数据需另行迁移，不能认为 clone 已包含。

## 验证

- 新地址 `ls-remote --symref`、fetch、push dry-run 成功；随后真实 `git push origin HEAD:refs/heads/wlc` 将 `a6bb2ae..ea983f2` 推送成功，推送后左右差为 `0 0`。
- 迁移实现提交 `962a270`（标签 `repo-migration-wulincong-20261103`）使用 `git push --atomic origin HEAD:refs/heads/wlc --tags` 成功发布。随后用 `ls-remote` 对照本地全部标签，实测当时 38 个标签的 SHA 全部一致，远端 `wlc` 与本机 HEAD 一致。验收记录的后续文档提交按相同约定另行 commit/tag 并推送。
- `cd web && npm run build` 通过（vue-tsc + Vite）；`git diff --check` 通过。仅 URL、说明和技能分发方式变更，无后端协议或数据库查询变更。
- 内置前在全新临时目录执行 `git clone --branch wlc --recurse-submodules git@github.com:wulincong/skill-plaza-foru.git …`，主仓库和 `career-guidance` 固定提交成功，随后 chart 子模块失败：`upload-pack: not our ref 75e10d00fbbcbc7c60cf50e678385afbfe434eb8`。临时目录已清理；这是现有子模块不可恢复的实测原因。
- 本机在已有对象的 chart 子仓库执行 `git fetch origin <完整SHA>` 曾返回成功；全新克隆证伪了它作为远端可恢复性证据的有效性。已持有对象的 fetch 不能替代独立仓库取回固定 SHA 的验收。
- 使用当前 SSH 身份 `wulincong` 对旧 chart 子仓库新建分支做 push dry-run，明确返回 `Permission … denied to wulincong`；新地址 `git@github.com:wulincong/chart-visualization-skill.git` 返回 `Repository not found`（不存在或当前身份不可访问）。没有实际写入原子仓库。用户选择内置后才执行分发方式变更。
- 内置前登记全部 21 个文件的 SHA-256、Git blob 与 mode，内置后逐项比对全部一致，没有遗漏或文件内容变化。`node .agents/skills/chart-visualization/scripts/validate-resources.mjs` 通过：广东 21/21 边界、42 别名，浙江 11/11 边界、22 别名。
- 从新远端全新执行 `git clone --branch wlc --recurse-submodules …`，实测提交 `962a270b025194448a58c2bdba70e550f0c71b0c` 检出成功，剩余三个外部子模块均正常取回原固定 SHA，工作目录 clean。chart 目录为主仓库普通文件，全部 21 个文件的 SHA-256 与内置前一致；新副本中区域资源校验再次通过（两省 2/2）。临时克隆已清理。验收证据保留于 gitignored 的 `web/server/traces/repository-migration-acceptance-20261103.json`，包含实际远端、检出提交、子模块 SHA、21 文件哈希及通过状态。

## 成本与取舍

- 保留当前开发分支及其余三个子仓库地址，没有使用 `push --mirror`、`--force` 或批量推送落后于远端的旧本地分支；新远端已有其余远程分支，迁移只需补齐当前分支及本地标签。
- 主仓库链接替换限制在主仓库跟踪的源文件内，独立技能仓库地址及历史来源不改；既有未提交的 `wechat-report/assets/brand.json` 不纳入迁移提交。
- 用户选择内置 chart，省去新建、授权和维护独立远端的成本；代价是图表规范的后续历史进入主仓库，不能再在该路径使用独立子仓库 push。已有 `dfcdafa`/`75e10d0` 的全部内容保留，旧未发布提交的原始来源记录在本条中。没有改用会丢失雷达/桑基规范的远端默认提交，也没有把独立 Git 历史混入主仓库的专用分支来绕过缺失远端。
- 保留 GitHub 当前默认分支，克隆示例显式指定 `wlc`；仅切换本地 `origin/HEAD` 不能解决 GitHub 首页/不带分支克隆仍指向旧默认分支的问题。

## 后续扩展路线

- 如确认 `wlc` 作为长期主线，可在 GitHub 仓库设置中将默认分支切换至 `wlc`，再运行 `git remote set-head origin -a` 同步本机；当前机器只有 Git SSH 实测能力，未验证 GitHub 管理 API 权限。
- 独立 skill 仓库若也迁移，应逐个验证新地址可取得当前固定 SHA，修改 `.gitmodules` 后执行 `git submodule sync --recursive`，并再次做全新递归克隆验收。
- GitHub Issues、权限、Actions secrets、保护规则等服务端设置不由 Git 分支/标签推送搬运；本次只核实代码远程迁移，不声称这些元数据已验证或迁移。


## 2026-11-04 · 其余三个技能纳入主仓库

**状态**　已实现。技能随维护分支一次检出，源码、资源和文档在同一次提交中维护。项目目录与新增技能约定见 `README.md:133`。

| 技能 | 原固定提交 | 原有跟踪文件 |
| --- | --- | ---: |
| career-guidance | `53f621a6ee4e6d04c9a4a9e0ff9243a35d09732a` | 22 |
| foru-web-ui | `85eae3763b1db10437398de2a01bf316923f5dc3` | 31 |
| industry-education-report | `37417a294ab68ab5975dc16adb74920050e61a3a` | 13 |

迁移前核实三个工作区均干净、检出提交与主仓库固定值一致。移除 gitlink、工作区的 Git 指针文件、相应本地配置和根 .gitmodules，按原路径将文件加入主仓库索引。逐一比对原始 66 个文件的 Git blob 和 mode 后，只修订三个技能 README 的维护说明，并将原主仓库配套指南移至各自 docs/index.md。当前索引没有 160000 项。本机历史 Git 对象留作读取旧版本之用。

用户选择以主仓库维护技能。后续源码修改与指南同版发布，代价是技能变更进入主仓库历史。重新挂载独立仓库会再次引入上游写权限与递归克隆依赖。需要追溯迁移前版本时可按表中的提交查阅。

本机对当前主仓库执行 `git clone --no-local --branch wlc`，以普通克隆检出迁移提交 `60c4933`。三个技能均能读取完整文件与自己的 docs。逐项复核全部 66 个原有文件的存在性和 mode，除三个已注明改写的 README 外，其余 63 个文件的内容哈希与迁移前一致。`git submodule status` 为空，克隆内的产业报告技能 11 项回归通过。
