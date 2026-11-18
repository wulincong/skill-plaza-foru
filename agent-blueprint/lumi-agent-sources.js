(() => {
  const region = document.querySelector('[data-agent-sources]');
  if (!region) return;
  const controls = region.querySelector('.agent-source-controls');
  const buttons = [...controls.querySelectorAll('button[data-source]')];
  const agents = [...region.querySelectorAll('.agent-list > li[data-sources]')];
  const status = controls.querySelector('[role="status"]');
  const allAgentsStatus = `显示全部 ${agents.length} 个`;
  let selected = '';
  status.textContent = allAgentsStatus;
  controls.hidden = false;
  region.classList.add('has-source-controls');
  buttons.forEach(button => {
    button.addEventListener('click', () => {
      selected = selected === button.dataset.source ? '' : button.dataset.source;
      buttons.forEach(item => item.setAttribute('aria-pressed', String(item.dataset.source === selected)));
      let count = 0;
      agents.forEach(agent => {
        const matches = agent.dataset.sources.split(' ').includes(selected);
        agent.classList.toggle('source-match', Boolean(selected) && matches);
        agent.classList.toggle('source-muted', Boolean(selected) && !matches);
        if (matches) count++;
      });
      status.textContent = selected ? `已突出 ${count} 个智能体` : allAgentsStatus;
    });
  });
})();
