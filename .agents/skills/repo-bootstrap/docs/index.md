# 初始化仓库协作约定

在新 Git 仓库中建立项目开发手记、项目级协作约定和 Issue 生命周期脚本。开始前先确认目标仓库根目录，以及 GitHub 远端是否用于这个项目。

## 初始化与检查

从目标仓库根目录运行技能内的 `scripts/init_repo.sh`。如果目标文件已存在，先阅读脚本报告的冲突，并逐一决定保留或合并哪些约定。运行后重点检查生成的 AGENTS.md 和项目手记是否指向目标项目自己的路径。

## 跟踪一项任务

确认需要 Issue 关联时，运行目标仓库的 `scripts/install-task-hooks.sh`。准备一份含范围与验收条件的计划文件，再用 `scripts/start-task.sh "任务标题" 计划文件` 将任务绑定到 Issue。这一步需要已登录的 GitHub CLI。

提交后检查提交说明里的 Task-Issue 编号。成功推送后由 GitHub Actions 关闭对应 Issue。新的长期决策写进生成的手记，并附真实的文件位置与验证结果。

[决策记录模板](../references/decision-record.md) · [Issue 正文模板](../references/issue-template.md)
