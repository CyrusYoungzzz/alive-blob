/**
 * Emoji Particle System — Canvas overlay for image-type characters.
 * Each emotion has themed emojis, spawn rate, and overlay effects.
 */
const Particles = (() => {
  const canvas = document.getElementById('particles');
  const ctx = canvas.getContext('2d');
  const W = 480, H = 480;
  let particles = [];
  let currentEmotion = 'calm';
  let animId = null;
  let active = false;

  const CONFIGS = {
    calm:    { spawn: 0.08, emojis: ['🌊','💧','🍃','✨','🫧'],  sizeMin: 18, sizeMax: 30, speedY: -0.5,  life: 160, spread: true  },
    happy:   { spawn: 0.25, emojis: ['😄','🌟','💛','🎉','🌈'],  sizeMin: 18, sizeMax: 32, speedY: -1.5,  life: 100, spread: true  },
    excited: { spawn: 0.5,  emojis: ['🔥','⚡','💥','🚀','🤩'],  sizeMin: 16, sizeMax: 36, speedY: -2.5,  life: 60,  spread: true  },
    curious: { spawn: 0.1,  emojis: ['❓','🔍','💡','👀','🤔'],  sizeMin: 22, sizeMax: 36, speedY: -0.7,  life: 140, spread: false },
    sleepy:  { spawn: 0.05, emojis: ['💤','🌙','⭐','☁️'],        sizeMin: 22, sizeMax: 40, speedY: -0.4,  life: 200, spread: false },
    shy:     { spawn: 0.12, emojis: ['💕','🌸','😳','💗','🎀'],  sizeMin: 14, sizeMax: 26, speedY: -0.6,  life: 130, spread: false },
    grumpy:  { spawn: 0.35, emojis: ['💢','😤','🔥','⚡','💨'],  sizeMin: 16, sizeMax: 32, speedY:  1.5,  life: 70,  spread: true  },
  };

  function spawnParticle() {
    const cfg = CONFIGS[currentEmotion] || CONFIGS.calm;
    if (Math.random() > cfg.spawn) return;

    const emoji = cfg.emojis[Math.random() * cfg.emojis.length | 0];
    const size = cfg.sizeMin + Math.random() * (cfg.sizeMax - cfg.sizeMin);

    let x, y;
    if (cfg.spread) {
      x = 40 + Math.random() * 400;
      y = cfg.speedY > 0 ? -20 : H + 20;
    } else {
      x = 160 + Math.random() * 160;
      y = cfg.speedY > 0 ? -10 : 180 + Math.random() * 60;
    }

    particles.push({
      x, y, emoji, size,
      vx: (Math.random() - 0.5) * 1.8,
      vy: cfg.speedY * (0.6 + Math.random() * 0.8),
      life: cfg.life,
      maxLife: cfg.life,
      rot: 0,
      rotV: (Math.random() - 0.5) * 0.08,
    });
  }

  function drawOverlays() {
    // Shy: pink blush glow on cheeks
    if (currentEmotion === 'shy') {
      ctx.save();
      [[150, 260], [330, 260]].forEach(([cx, cy]) => {
        const g = ctx.createRadialGradient(cx, cy, 8, cx, cy, 65);
        g.addColorStop(0, 'rgba(255,100,130,0.35)');
        g.addColorStop(1, 'rgba(255,100,130,0)');
        ctx.fillStyle = g;
        ctx.fillRect(cx - 70, cy - 70, 140, 140);
      });
      ctx.restore();
    }
    // Grumpy: tear streaks
    if (currentEmotion === 'grumpy') {
      ctx.save();
      ctx.fillStyle = 'rgba(100,180,255,0.2)';
      ctx.beginPath(); ctx.ellipse(190, 300, 7, 38, 0, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.ellipse(290, 305, 7, 40, 0.1, 0, Math.PI * 2); ctx.fill();
      ctx.restore();
    }
    // Sleepy: vignette darken
    if (currentEmotion === 'sleepy') {
      const g = ctx.createRadialGradient(W / 2, H / 2, 80, W / 2, H / 2, 240);
      g.addColorStop(0, 'rgba(0,0,0,0)');
      g.addColorStop(1, 'rgba(0,0,20,0.45)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
    }
    // Excited: warm radial flash
    if (currentEmotion === 'excited') {
      const t = Date.now() * 0.003;
      const pulse = 0.08 + Math.sin(t * 5) * 0.06;
      const g = ctx.createRadialGradient(W / 2, H / 2, 40, W / 2, H / 2, 240);
      g.addColorStop(0, `rgba(255,180,50,${pulse})`);
      g.addColorStop(1, 'rgba(255,80,0,0)');
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
    }
  }

  function frame() {
    if (!active) return;
    animId = requestAnimationFrame(frame);

    ctx.clearRect(0, 0, W, H);
    drawOverlays();
    spawnParticle();

    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.rot += p.rotV;
      p.life--;

      if (p.life <= 0 || p.x < -50 || p.x > W + 50 || p.y < -50 || p.y > H + 50) {
        particles.splice(i, 1);
        continue;
      }

      // fade in then fade out
      const fadeIn = Math.min(1, (p.maxLife - p.life) / 12);
      const fadeOut = Math.min(1, p.life / (p.maxLife * 0.25));
      const alpha = fadeIn * fadeOut;

      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.font = `${p.size}px serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(p.emoji, 0, 0);
      ctx.restore();
    }
  }

  function setEmotion(emotion) {
    if (emotion === currentEmotion) return;
    currentEmotion = emotion;
    // let old particles fade naturally
    particles.forEach(p => p.life = Math.min(p.life, 18));
    // burst on switch
    for (let i = 0; i < 6; i++) spawnParticle();
  }

  function start() {
    if (!active) { active = true; frame(); }
  }

  function stop() {
    active = false;
    if (animId) { cancelAnimationFrame(animId); animId = null; }
    particles = [];
    ctx.clearRect(0, 0, W, H);
  }

  return { start, stop, setEmotion };
})();
