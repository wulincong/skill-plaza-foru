(() => {
  "use strict";
  const background = document.querySelector(".page-background");
  if (!background) return;

  const canvas = document.createElement("canvas");
  canvas.className = "page-background-grid";
  canvas.setAttribute("aria-hidden", "true");
  const ctx = canvas.getContext("2d");
  if (!ctx) return; // The CSS grid remains visible if Canvas is unavailable.
  background.append(canvas);

  const desktop = matchMedia("(min-width: 768px)");
  const pointerDevice = matchMedia("(hover: hover) and (pointer: fine)");
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const forcedColors = matchMedia("(forced-colors: active)");
  const printing = matchMedia("print");
  const spacing = 90;
  const radius = 160;
  let nodes = [];
  let columns = 0;
  let width = 0;
  let height = 0;
  let pointer = null;
  let enabled = false;
  let frame = 0;
  let lastPaint = 0;

  function stop() {
    cancelAnimationFrame(frame);
    frame = 0;
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);
    // Short gaps around each point keep the network light and legible.
    nodes.forEach((point, index) => {
      const neighbors = [];
      if ((index + 1) % columns) neighbors.push(nodes[index + 1]);
      if (index + columns < nodes.length) neighbors.push(nodes[index + columns]);
      neighbors.forEach((neighbor) => {
        const dx = neighbor.x - point.x;
        const dy = neighbor.y - point.y;
        const length = Math.hypot(dx, dy);
        if (length < 22) return;
        const gap = 10 / length;
        const emphasis = (point.depth + neighbor.depth) / 2;
        ctx.lineWidth = .5 + emphasis * .25;
        ctx.strokeStyle = `rgba(60,100,160,${.1 + emphasis * .12})`;
        ctx.beginPath();
        ctx.moveTo(point.x + dx * gap, point.y + dy * gap);
        ctx.lineTo(neighbor.x - dx * gap, neighbor.y - dy * gap);
        ctx.stroke();
      });
    });
    nodes.forEach((point) => {
      ctx.fillStyle = `rgba(60,100,160,${.2 + point.depth * .4})`;
      ctx.beginPath();
      ctx.arc(point.x, point.y, 1.8 + point.depth * 2, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  function animate(time) {
    frame = 0;
    if (!enabled || document.hidden) return;
    if (time - lastPaint < 1000 / 30) {
      frame = requestAnimationFrame(animate);
      return;
    }
    lastPaint = time;
    let moving = false;
    nodes.forEach((point) => {
      const dx = pointer ? point.homeX - pointer.x : 0;
      const dy = pointer ? point.homeY - pointer.y : 0;
      const distance = Math.hypot(dx, dy);
      const influence = pointer ? Math.max(0, 1 - distance / radius) : 0;
      const weight = influence * influence * (3 - 2 * influence);
      // A local displacement plus changing point size gives the mesh its depth cue.
      const shift = distance > .01 ? 28 * weight / distance : 0;
      const targetX = point.homeX + dx * shift;
      const targetY = point.homeY + dy * shift;
      point.vx = (point.vx + (targetX - point.x) * .12) * .72;
      point.vy = (point.vy + (targetY - point.y) * .12) * .72;
      point.x += point.vx;
      point.y += point.vy;
      point.depth += (weight - point.depth) * .22;
      const unsettled = Math.abs(targetX - point.x) + Math.abs(targetY - point.y)
        + Math.abs(point.vx) + Math.abs(point.vy) + Math.abs(weight - point.depth);
      if (unsettled > .015) moving = true;
      else {
        point.x = targetX;
        point.y = targetY;
        point.depth = weight;
        point.vx = point.vy = 0;
      }
    });
    draw();
    // Wake on input, then stop repainting once the mesh has settled.
    if (moving) frame = requestAnimationFrame(animate);
  }

  function wake() {
    if (enabled && !document.hidden && !frame) frame = requestAnimationFrame(animate);
  }

  function clearPointer() {
    pointer = null;
    wake();
  }

  function rebuild() {
    stop();
    enabled = desktop.matches && pointerDevice.matches && !reducedMotion.matches
      && !forcedColors.matches && !printing.matches && !document.hidden;
    background.classList.remove("has-live-grid");
    pointer = null;
    if (!enabled) {
      nodes = [];
      canvas.width = canvas.height = 1;
      return;
    }
    width = innerWidth;
    height = innerHeight;
    const ratio = Math.min(devicePixelRatio || 1, 1.5);
    canvas.width = Math.ceil(width * ratio);
    canvas.height = Math.ceil(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    columns = Math.ceil(width / spacing) + 1;
    const rows = Math.ceil(height / spacing) + 1;
    const startX = (width - (columns - 1) * spacing) / 2;
    const startY = (height - (rows - 1) * spacing) / 2;
    nodes = Array.from({ length: columns * rows }, (_, index) => {
      const x = startX + index % columns * spacing;
      const y = startY + Math.floor(index / columns) * spacing;
      return { homeX: x, homeY: y, x, y, vx: 0, vy: 0, depth: 0 };
    });
    draw();
    background.classList.add("has-live-grid");
  }

  window.addEventListener("pointermove", (event) => {
    if (!enabled || event.pointerType === "touch") return;
    pointer = { x: event.clientX, y: event.clientY };
    wake();
  }, { passive: true });
  document.addEventListener("pointerleave", clearPointer, { passive: true });
  window.addEventListener("blur", clearPointer);
  window.addEventListener("resize", rebuild, { passive: true });
  document.addEventListener("visibilitychange", rebuild);
  [desktop, pointerDevice, reducedMotion, forcedColors, printing].forEach((query) => {
    query.addEventListener("change", rebuild);
  });
  rebuild();
})();
