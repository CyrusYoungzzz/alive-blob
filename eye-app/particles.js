/**
 * 粒子系统 — Canvas 叠加层动画
 * 每种情绪有独特的粒子效果
 */
const Particles = (() => {
  const canvas = document.getElementById('particles');
  const ctx = canvas.getContext('2d');
  let particles = [];
  let currentEmotion = 'calm';
  let animId = null;

  // 粒子配置
  const CONFIGS = {
    calm: { spawn: 0, symbols: [] },  // 无粒子
    happy: { spawn: 0.15, symbols: ['❤️', '✨', '⭐'], sizeMin: 16, sizeMax: 28, speedY: -1.5, life: 80, spread: true },
    excited: { spawn: 0.4, symbols: ['⚡', '🔥', '💥', '✨', '🌟'], sizeMin: 14, sizeMax: 32, speedY: -2.5, life: 50, spread: true },
    curious: { spawn: 0.06, symbols: ['❓', '🤔', '💭'], sizeMin: 24, sizeMax: 36, speedY: -0.8, life: 120, spread: false },
    sleepy: { spawn: 0.04, symbols: ['💤'], sizeMin: 20, sizeMax: 40, speedY: -0.5, life: 150, spread: false },
    shy: { spawn: 0.08, symbols: ['💗', '😳'], sizeMin: 14, sizeMax: 22, speedY: -0.6, life: 100, spread: false },
    grumpy: { spawn: 0.2, symbols: ['💢', '😤', '💧'], sizeMin: 16, sizeMax: 30, speedY: 1.5, life: 60, spread: true },
  };

  function spawnParticle() {
    const cfg = CONFIGS[currentEmotion];
    if (!cfg || cfg.spawn === 0) return;
    if (Math.random() > cfg.spawn) return;

    const symbol = cfg.symbols[Math.floor(Math.random() * cfg.symbols.length)];
    const size = cfg.sizeMin + Math.random() * (cfg.sizeMax - cfg.sizeMin);

    let x, y;
    if (cfg.spread) {
      // 从屏幕各处冒出
      x = 60 + Math.random() * 360;
      y = cfg.speedY > 0 ? -20 : 500;  // grumpy 从上往下，其他从下往上
    } else {
      // 从头顶区域冒出
      x = 180 + Math.random() * 120;
      y = cfg.speedY > 0 ? 0 : 160;
    }

    particles.push({
      x,
      y,
      vx: (Math.random() - 0.5) * 1.5,
      vy: cfg.speedY * (0.7 + Math.random() * 0.6),
      size,
      symbol,
      life: cfg.life,
      maxLife: cfg.life,
      rotation: Math.random() * 0.5 - 0.25,
    });
  }

  function update() {
    ctx.clearRect(0, 0, 480, 480);

    // Shy: 脸颊泛红光晕
    if (currentEmotion === 'shy') {
      ctx.save();
      const gradient1 = ctx.createRadialGradient(150, 260, 10, 150, 260, 70);
      gradient1.addColorStop(0, 'rgba(255, 100, 130, 0.35)');
      gradient1.addColorStop(1, 'rgba(255, 100, 130, 0)');
      ctx.fillStyle = gradient1;
      ctx.fillRect(80, 190, 140, 140);

      const gradient2 = ctx.createRadialGradient(330, 260, 10, 330, 260, 70);
      gradient2.addColorStop(0, 'rgba(255, 100, 130, 0.35)');
      gradient2.addColorStop(1, 'rgba(255, 100, 130, 0)');
      ctx.fillStyle = gradient2;
      ctx.fillRect(260, 190, 140, 140);
      ctx.restore();
    }

    // Grumpy: 眼泪轨迹
    if (currentEmotion === 'grumpy') {
      ctx.save();
      ctx.fillStyle = 'rgba(100, 180, 255, 0.25)';
      // 左眼泪痕
      ctx.beginPath();
      ctx.ellipse(190, 300, 8, 40, 0, 0, Math.PI * 2);
      ctx.fill();
      // 右眼泪痕
      ctx.beginPath();
      ctx.ellipse(290, 305, 8, 42, 0.1, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    // 生成新粒子
    spawnParticle();

    // 更新和绘制粒子
    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.life--;
      p.rotation += 0.02;

      const alpha = Math.min(1, p.life / p.maxLife * 2);

      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rotation);
      ctx.font = `${p.size}px serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(p.symbol, 0, 0);
      ctx.restore();

      if (p.life <= 0 || p.x < -50 || p.x > 530 || p.y < -50 || p.y > 530) {
        particles.splice(i, 1);
      }
    }

    animId = requestAnimationFrame(update);
  }

  function setEmotion(emotion) {
    currentEmotion = emotion;
    // 清除旧粒子（平滑过渡：让旧粒子自然消亡）
    particles.forEach(p => p.life = Math.min(p.life, 15));
  }

  function start() {
    if (!animId) update();
  }

  function stop() {
    if (animId) {
      cancelAnimationFrame(animId);
      animId = null;
    }
    ctx.clearRect(0, 0, 480, 480);
    particles = [];
  }

  return { setEmotion, start, stop };
})();
