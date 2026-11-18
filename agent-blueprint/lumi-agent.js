(() => {
  "use strict";
  const buttons = Array.from(document.querySelectorAll(".cycle-step"));
  const next = document.querySelector(".runtime-next");
  if (!buttons.length || !next) return;

  const steps = [
    { title: "接收任务", copy: "运行时接收用户目标和输入，建立任务状态。编排系统按需拆分子任务，并设置权限、调用预算与最大轮次。", systems: "运行时引擎 · 编排系统 · 安全层" },
    { title: "组装上下文", copy: "State 读取当前进度、工具结果与待办事项，记忆子系统检索相关知识和历史经验。运行时在上下文预算内整理本轮模型输入。", systems: "运行时引擎 / State · 记忆子系统" },
    { title: "LLM 规划", copy: "LLM 结合目标和上下文，提出下一步行动、工具调用或候选答案。Flow 根据输出决定后续路径；无须工具时，可直接进入结果校验。", systems: "LLM · 运行时引擎 / Flow · 编排系统" },
    { title: "受控执行", copy: "工具层校验参数，安全层检查权限与审批要求。通过检查后，工具在允许的环境中访问 API、数据库、文件、Shell 或网络，并返回实际执行结果。", systems: "工具层 · 安全层 · 外部环境" },
    { title: "回写反馈", copy: "运行时将工具结果或错误回写 State。记忆子系统按策略保存有价值的经验，观测层记录本轮调用、耗时与成本，为下一轮提供可追踪的反馈。", systems: "运行时引擎 / State · 记忆子系统 · 观测层" },
    { title: "判断与交付", copy: "运行时判断目标是否完成，输出治理校验候选结果。满足条件则交付；仍需行动则返回组装上下文；达到预算、轮次或风险边界时，受控停止或交由人工处理。", systems: "运行时引擎 / Loop · 输出治理 · 安全层" }
  ];
  let current = 1;
  const select = (step) => {
    current = step;
    const detail = steps[step - 1];
    buttons.forEach((button) => {
      const active = Number(button.dataset.step) === step;
      button.classList.toggle("is-active", active);
      button.parentElement.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    document.querySelectorAll("[data-flow-step]").forEach((path) => {
      path.classList.toggle("is-active", Number(path.dataset.flowStep) === step);
    });
    document.getElementById("runtime-detail-index").textContent = `${String(step).padStart(2, "0")} / 06`;
    document.getElementById("runtime-detail-title").textContent = detail.title;
    document.getElementById("runtime-detail-copy").textContent = detail.copy;
    document.getElementById("runtime-detail-systems").textContent = `协作子系统：${detail.systems}`;
    next.firstChild.textContent = step === 6 ? "继续下一轮 " : "下一步 ";
    document.querySelector(".runtime-cycle").classList.toggle("is-looping", step === 6);
  };
  buttons.forEach((button) => button.addEventListener("click", () => select(Number(button.dataset.step))));
  next.addEventListener("click", () => select(current === 6 ? 2 : current + 1));
  next.hidden = false;
})();
