# 003 开发任务 GitHub issue 生命周期与 push 关闭

- 状态：已实现（GitHub 认证后待实测）。
- 动机：让每次开发先留下总结后的计划，并把完成状态与成功推送绑定，避免只在聊天上下文中保留计划或在失败推送后误关闭任务。
- 约定细节：
  - `scripts/start-task.sh <计划标题> <计划文件>` 使用 `gh issue create` 创建 issue，正文包含计划文件内容、仓库、分支、创建时提交和完成方式；issue 编号记录在 `.git/task-issue`，URL 记录在 `.git/task-issue-url`。
  - `.githooks/pre-commit` 与 `.githooks/pre-push` 要求 `.git/task-issue` 存在且为数字编号。
  - `.githooks/prepare-commit-msg` 将 `Task-Issue: #<number>` 追加到提交信息；`.github/workflows/close-task-issue.yml` 在任意分支的 push 成功后解析提交信息，并用 GitHub Actions token 关闭 issue。
  - `scripts/install-task-hooks.sh` 设置 `core.hooksPath=.githooks`。实现位置：`scripts/start-task.sh:16-46`、`.githooks/pre-commit:3-10`、`.githooks/prepare-commit-msg:3-10`、`.github/workflows/close-task-issue.yml:3-26`。
- 成本与取舍：Git 没有原生 `post-push` hook，且 Git alias 不能覆盖内置 `git push`；因此关闭动作放到 GitHub Actions 的 push 事件中。活动编号保存在 `.git`，仅通过提交 trailer 传播；创建 issue 依赖本机 `gh` 登录，关闭 issue 依赖仓库 Actions 的 `issues: write` 权限。
- 后续扩展路线：认证后验证创建 issue、提交拦截、成功 push 关闭和失败 push 保持开启；当前 Actions 已覆盖团队共享场景。

2026-10-23 本机状态核对：当前检出未设置 `core.hooksPath`，`.git/task-issue` 也不存在，故上述 hooks 的脚本存在但本机未启用。项目 AGENTS.md 已明确每轮验证完成后正常 `git commit`，再给当前分支提交打标签并在最终回复列出；不用脱离当前分支的工作区快照代替。此前三个已验证快照标签已沿祖先关系快进到当前分支，工作文件核对一致后才移动分支，未改变文件内容。本次保留原图使用普通本地提交与标签；GitHub issue/push 自动生命周期仍待启用后验证。
