import { useEffect, useRef } from "react";

/** Cursor glow + trail, same as auth page. Light panel only — no dark-panel branch. */
export default function AmbientLight() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context || !window.matchMedia("(hover: hover) and (pointer: fine)").matches || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let frame = 0;
    let width = window.innerWidth;
    let height = window.innerHeight;
    let pointer = { x: width / 2, y: height / 2 };
    let light = { ...pointer };
    let speed = 0;
    let lastMove = 0;
    let lastTime = 0;
    let points: Array<{ x: number; y: number; time: number }> = [];

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const move = (event: PointerEvent) => {
      if (event.pointerType === "touch") return;
      const now = performance.now();
      const elapsed = Math.max(1, now - lastTime);
      const distance = Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y);
      speed = Math.min(1, distance / elapsed / 1.2);
      pointer = { x: event.clientX, y: event.clientY };
      points.push({ ...pointer, time: now });
      if (points.length > 24) points.shift();
      lastMove = now;
      if (!frame) frame = requestAnimationFrame(draw);
      lastTime = now;
    };
    const draw = (now: number) => {
      frame = 0;
      context.clearRect(0, 0, width, height);
      const settle = now - lastMove > 1000;
      speed += ((settle ? 0 : speed) - speed) * 0.035;
      light.x += (pointer.x - light.x) * 0.16;
      light.y += (pointer.y - light.y) * 0.16;
      points = points.filter((point) => now - point.time < 520);

      if (points.length > 1) {
        for (let index = 1; index < points.length; index += 1) {
          const start = points[index - 1];
          const end = points[index];
          const alpha = Math.max(0, 1 - (now - end.time) / 520) * 0.3 * (0.72 + speed * 0.28);
          context.beginPath();
          context.moveTo(start.x, start.y);
          context.lineTo(end.x, end.y);
          context.lineCap = "round";
          context.lineWidth = 1.6;
          context.strokeStyle = `rgba(79, 134, 247, ${alpha})`;
          context.shadowBlur = 7;
          context.shadowColor = "rgba(79, 134, 247, 0.32)";
          context.stroke();
        }
      }

      const opacity = Math.max(0, 0.7 - (now - lastMove) / 2200);
      const radius = 150 + speed * 24;
      const glow = context.createRadialGradient(light.x, light.y, 0, light.x, light.y, radius);
      glow.addColorStop(0, `rgba(79, 134, 247, ${opacity * (0.16 + speed * 0.05)})`);
      glow.addColorStop(0.34, `rgba(107, 130, 203, ${opacity * 0.09})`);
      glow.addColorStop(0.72, `rgba(157, 140, 255, ${opacity * 0.025})`);
      glow.addColorStop(1, "rgba(157, 140, 255, 0)");
      context.shadowBlur = 0;
      context.fillStyle = glow;
      context.fillRect(light.x - radius, light.y - radius, radius * 2, radius * 2);

      if (now - lastMove < 2400 || points.length > 0) frame = requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", move, { passive: true });
    return () => {
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", move);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden="true" className="auth-ambient-canvas" />;
}
