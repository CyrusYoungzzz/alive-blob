/** Alive Blob — Character Showcase Controller */
(() => {
  const API = '';
  const ENGINE_WS = `ws://${location.hostname}:8000/ws/mobile`;

  const EMOTIONS = [
    { id: 'calm',    emoji: '😌', label: '平静',  color: '#4A7BFF' },
    { id: 'happy',   emoji: '😄', label: '开心',  color: '#E84593' },
    { id: 'excited', emoji: '🤩', label: '兴奋',  color: '#FF6B2B' },
    { id: 'curious', emoji: '🤔', label: '好奇',  color: '#2ECC87' },
    { id: 'sleepy',  emoji: '😴', label: '困倦',  color: '#5C5C70' },
    { id: 'shy',     emoji: '😳', label: '害羞',  color: '#FF9EB5' },
    { id: 'grumpy',  emoji: '😤', label: '不爽',  color: '#C0392B' },
  ];

  const BUILTIN = [
    { id: 'cube', name: 'Cube', desc: 'Alive Blob', type: '3d',
      avatar: null },
    { id: 'keji-shu', name: '科技薯', desc: '电子狗有狗点子', type: 'image',
      avatar: 'https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo3154311m61e6g5pkcpsk0uc8t76cabeo?imageView2/2/w/540/format/webp' },
  ];

  let ws = null, currentCharId = 'cube', currentEmotion = 'calm';
  let rankings = [], totalInteractions = 0, lastHitTs = null;

  /* ── Slider ── */
  const slider = document.getElementById('slider');
  slider.classList.add('p1');

  let tx0 = 0;
  slider.addEventListener('touchstart', e => { tx0 = e.touches[0].clientX; }, { passive: true });
  slider.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - tx0;
    if (dx < -50) goPage(2);
    else if (dx > 50) goPage(1);
  }, { passive: true });

  /* mouse swipe for desktop */
  let mx0 = 0, mDown = false;
  slider.addEventListener('mousedown', e => { mx0 = e.clientX; mDown = true; });
  slider.addEventListener('mouseup', e => { if (!mDown) return; mDown = false; const dx = e.clientX - mx0; if (dx < -50) goPage(2); else if (dx > 50) goPage(1); });
  slider.addEventListener('mouseleave', () => { mDown = false; });

  document.addEventListener('keydown', e => { if (e.key === 'ArrowRight') goPage(2); else if (e.key === 'ArrowLeft') goPage(1); });
  document.getElementById('btn-back').addEventListener('click', () => goPage(1));

  /* dot navigation */
  document.querySelectorAll('.dots').forEach(wrap => {
    wrap.querySelectorAll('.dot').forEach((d, i) => {
      d.style.cursor = 'pointer';
      d.addEventListener('click', () => goPage(i + 1));
    });
  });

  function goPage(n) {
    slider.className = n === 2 ? 'p2' : 'p1';
    if (n === 2) { refreshList(); startCamera(); loadFaceModel(); }
    else stopCamera();
  }

  /* ── WebSocket ── */
  function connectWS() {
    ws = new WebSocket(ENGINE_WS);
    ws.onopen = () => document.getElementById('conn-dot').classList.add('on');
    ws.onclose = () => { document.getElementById('conn-dot').classList.remove('on'); setTimeout(connectWS, 2000); };
    ws.onmessage = e => {
      const d = JSON.parse(e.data);
      if (d.type === 'state_sync') {
        if (d.character) currentCharId = d.character;
        if (d.emotion && d.emotion !== currentEmotion) { currentEmotion = d.emotion; syncUI(); }
      } else if (d.type === 'interaction_init') {
        rankings = d.rankings || [];
        totalInteractions = d.total || 0;
        lastHitTs = d.last_hit_ts || null;
        renderRanking();
      } else if (d.type === 'interaction_update') {
        rankings = d.rankings || [];
        totalInteractions = d.total || 0;
        lastHitTs = d.last_hit_ts || null;
        renderRanking(d.character);
      }
    };
    ws.onerror = () => ws.close();
  }
  function send(msg) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(msg)); }

  /* ── Emotion Chips ── */
  const chipsEl = document.getElementById('chips');
  EMOTIONS.forEach(em => {
    const b = document.createElement('button');
    b.className = 'chip';
    b.dataset.id = em.id;
    b.innerHTML = `<span class="cd" style="background:${em.color};color:${em.color}"></span>${em.emoji} ${em.label}`;
    b.onclick = () => { send({ type: 'set_emotion', emotion: em.id }); currentEmotion = em.id; syncUI(); };
    chipsEl.appendChild(b);
  });

  function syncUI() {
    document.querySelectorAll('.chip').forEach(c => c.classList.toggle('on', c.dataset.id === currentEmotion));
    const em = EMOTIONS.find(e => e.id === currentEmotion);
    document.getElementById('emotion-name').textContent = currentEmotion;
    if (em) document.getElementById('emotion-name').style.color = em.color;
    // preview iframe receives emotion via engine WebSocket — no extra work needed
  }

  function switchChar(id, opts) {
    const ch = BUILTIN.find(b => b.id === id);
    const name = ch ? ch.name : (opts && opts.name || id);
    const desc = ch ? ch.desc : (opts && opts.desc || '');
    currentCharId = id;
    document.getElementById('char-name-display').textContent = name;
    document.getElementById('char-desc').textContent = desc;
    send({ type: 'switch_character', name: id });
  }

  /* ── Camera + Face Detection ── */
  const video = document.getElementById('cam-video');
  const overlay = document.getElementById('cam-overlay');
  const octx = overlay.getContext('2d');
  const camHint = document.getElementById('cam-hint');
  const btnShutter = document.getElementById('btn-shutter');
  const camStep = document.getElementById('cam-step');
  const faceStep = document.getElementById('face-step');
  const faceGrid = document.getElementById('face-grid');
  const faceCount = document.getElementById('face-count');
  const btnAddFaces = document.getElementById('btn-add-faces');
  const faceStatus = document.getElementById('face-status');

  let camStream = null, detectLoop = null, faceModelReady = false;
  let detectedFaces = []; // {box, canvas}

  // load face-api model (once)
  let modelLoading = false;
  async function loadFaceModel() {
    if (faceModelReady || modelLoading) return;
    modelLoading = true;
    try {
      await faceapi.nets.tinyFaceDetector.loadFromUri('/models');
      faceModelReady = true;
      camHint.textContent = '对准人脸，按 Space 拍摄';
      btnShutter.disabled = false;
    } catch (e) {
      camHint.textContent = '模型加载失败: ' + e.message;
      modelLoading = false;
    }
  }

  // start camera
  async function startCamera() {
    if (camStream) return;
    try {
      camStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
      video.srcObject = camStream;
      await video.play();
      overlay.width = video.videoWidth;
      overlay.height = video.videoHeight;
      startDetectLoop();
    } catch (e) {
      camHint.textContent = '无法访问摄像头: ' + e.message;
    }
  }

  function stopCamera() {
    if (detectLoop) { cancelAnimationFrame(detectLoop); detectLoop = null; }
    if (camStream) { camStream.getTracks().forEach(t => t.stop()); camStream = null; }
  }

  // real-time face detection overlay (green boxes)
  function startDetectLoop() {
    async function loop() {
      if (!camStream || !faceModelReady) { detectLoop = requestAnimationFrame(loop); return; }
      const detections = await faceapi.detectAllFaces(video, new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.4 }));

      octx.clearRect(0, 0, overlay.width, overlay.height);
      detections.forEach(d => {
        const b = d.box;
        octx.strokeStyle = '#4f8';
        octx.lineWidth = 2;
        octx.strokeRect(b.x, b.y, b.width, b.height);
      });

      const n = detections.length;
      if (n > 0) {
        camHint.classList.add('hidden');
      } else {
        camHint.textContent = '未检测到人脸';
        camHint.classList.remove('hidden');
      }

      detectLoop = requestAnimationFrame(loop);
    }
    loop();
  }

  // capture snapshot + extract faces
  async function captureAndDetect() {
    if (!faceModelReady) return;
    // take snapshot (mirrored to match display)
    const snap = document.createElement('canvas');
    snap.width = video.videoWidth;
    snap.height = video.videoHeight;
    const sctx = snap.getContext('2d');
    sctx.translate(snap.width, 0);
    sctx.scale(-1, 1);
    sctx.drawImage(video, 0, 0);

    // detect faces on the snapshot (higher res)
    const detections = await faceapi.detectAllFaces(snap, new faceapi.TinyFaceDetectorOptions({ inputSize: 416, scoreThreshold: 0.35 }));

    if (detections.length === 0) {
      camHint.textContent = '未检测到人脸，请重试';
      camHint.classList.remove('hidden');
      return;
    }

    // crop each face with padding
    detectedFaces = [];
    detections.forEach((d, i) => {
      const b = d.box;
      const pad = Math.max(b.width, b.height) * 0.35;
      const x = Math.max(0, b.x - pad) | 0;
      const y = Math.max(0, b.y - pad) | 0;
      const w = Math.min(snap.width - x, b.width + pad * 2) | 0;
      const h = Math.min(snap.height - y, b.height + pad * 2) | 0;
      const fc = document.createElement('canvas');
      fc.width = w; fc.height = h;
      fc.getContext('2d').drawImage(snap, x, y, w, h, 0, 0, w, h);
      detectedFaces.push({ canvas: fc, selected: true, name: '' });
    });

    showFaceSelection();
  }

  function showFaceSelection() {
    camStep.style.display = 'none';
    faceStep.style.display = '';
    faceCount.textContent = detectedFaces.length;

    faceGrid.innerHTML = '';
    detectedFaces.forEach((f, i) => {
      const card = document.createElement('div');
      card.className = 'face-card selected';
      const img = document.createElement('img');
      img.src = f.canvas.toDataURL('image/jpeg', 0.9);
      const check = document.createElement('div');
      check.className = 'face-check';
      check.textContent = '\u2713';
      const nameInput = document.createElement('input');
      nameInput.className = 'face-name';
      nameInput.type = 'text';
      nameInput.placeholder = '输入名称';
      nameInput.addEventListener('input', () => { f.name = nameInput.value.trim(); checkAddBtn(); });
      nameInput.addEventListener('click', e => e.stopPropagation());

      card.appendChild(img);
      card.appendChild(check);
      card.appendChild(nameInput);
      card.addEventListener('click', () => {
        f.selected = !f.selected;
        card.classList.toggle('selected', f.selected);
        checkAddBtn();
      });
      faceGrid.appendChild(card);
    });
    checkAddBtn();
  }

  function checkAddBtn() {
    const sel = detectedFaces.filter(f => f.selected && f.name);
    btnAddFaces.disabled = sel.length === 0;
    btnAddFaces.textContent = sel.length > 0 ? `添加 ${sel.length} 个角色` : '添加选中的人脸';
  }

  // retake
  document.getElementById('btn-retake').addEventListener('click', () => {
    faceStep.style.display = 'none';
    camStep.style.display = '';
    detectedFaces = [];
    startCamera();
  });

  // batch create characters from selected faces
  btnAddFaces.addEventListener('click', async () => {
    const selected = detectedFaces.filter(f => f.selected && f.name);
    if (!selected.length) return;
    btnAddFaces.disabled = true;
    faceStatus.textContent = `创建中... 0/${selected.length}`;

    for (let i = 0; i < selected.length; i++) {
      const f = selected[i];
      faceStatus.textContent = `创建中... ${i + 1}/${selected.length}`;
      try {
        const blob = await new Promise(r => f.canvas.toBlob(r, 'image/jpeg', 0.9));
        const fd = new FormData();
        fd.append('name', f.name);
        fd.append('photo', blob, `${f.name}.jpg`);
        const r = await fetch(`${API}/api/characters`, { method: 'POST', body: fd });
        if (!r.ok) {
          const e = await r.json();
          faceStatus.textContent = `${f.name}: ${e.detail || r.statusText}`;
          continue;
        }
        await poll(f.name);
      } catch (e) {
        faceStatus.textContent = `${f.name}: ${e.message}`;
      }
    }

    faceStatus.textContent = '全部完成!';
    refreshList();
    setTimeout(() => {
      faceStatus.textContent = '';
      // go back to camera step
      faceStep.style.display = 'none';
      camStep.style.display = '';
      detectedFaces = [];
    }, 2000);
  });

  // Space key to capture
  document.addEventListener('keydown', e => {
    if (e.code === 'Space' && camStep.style.display !== 'none' && faceModelReady) {
      e.preventDefault();
      captureAndDetect();
    }
  });

  btnShutter.addEventListener('click', () => captureAndDetect());

  async function poll(name) {
    const s = Date.now();
    while (Date.now() - s < 60000) {
      await new Promise(r => setTimeout(r, 1000));
      const r = await fetch(`${API}/api/characters/${name}`);
      if (!r.ok) continue;
      const d = await r.json();
      if (d.status === 'ready') return;
      if (d.status.startsWith('error')) throw new Error(d.status);
    }
    throw new Error('超时');
  }


  /* ── Character List ── */
  function renderBuiltin(el) {
    BUILTIN.forEach(b => {
      const d = document.createElement('div');
      d.className = 'citem' + (b.id === currentCharId ? ' cur' : '');
      const av = b.avatar
        ? `<img class="citem-av-img" src="${b.avatar}" alt="">`
        : `<span>${b.name[0]}</span>`;
      d.innerHTML = `<div class="citem-av">${av}</div>
        <div class="citem-info"><div class="n">${b.name}</div><div class="m">${b.desc} · 内置</div></div>
        <div class="citem-acts"><button class="use" title="使用">&#9654;</button></div>`;
      d.querySelector('.use').onclick = () => { switchChar(b.id); goPage(1); };
      el.appendChild(d);
    });
  }

  async function refreshList() {
    const el = document.getElementById('char-list');
    el.innerHTML = '';
    renderBuiltin(el);
    try {
      const r = await fetch(`${API}/api/characters`);
      const cs = await r.json();
      cs.forEach(c => {
        const d = document.createElement('div');
        d.className = 'citem' + (c.name === currentCharId ? ' cur' : '');
        const thumb = `/characters/${c.name}/source.jpg`;
        d.innerHTML = `<div class="citem-av"><img class="citem-av-img" src="${thumb}" alt="" onerror="this.style.display='none';this.parentNode.innerHTML='<span>${(c.display_name||c.name)[0].toUpperCase()}</span>'"></div>
          <div class="citem-info"><div class="n">${c.display_name||c.name}</div><div class="m">${c.emotions_ready}/${c.emotions_total} · ${c.status}</div></div>
          <div class="citem-acts"><button class="use" title="使用">&#9654;</button><button class="del" title="删除">&times;</button></div>`;
        d.querySelector('.use').onclick = () => {
          switchChar(c.name, { name: c.display_name || c.name, desc: `${c.emotions_ready}/${c.emotions_total} emotions`, avatar: thumb });
          goPage(1);
        };
        d.querySelector('.del').onclick = async () => { if(!confirm('删除 '+c.name+'？')) return; await fetch(`${API}/api/characters/${c.name}`,{method:'DELETE'}); refreshList(); };
        el.appendChild(d);
      });
    } catch {}
  }

  /* ── Ranking ── */
  function renderRanking(flashCharId) {
    const list = document.getElementById('rank-list');
    const maxCount = rankings.length ? rankings[0].count : 1;

    list.innerHTML = '';
    rankings.forEach(r => {
      const item = document.createElement('div');
      item.className = 'rank-item' + (r.name === currentCharId ? ' active' : '');
      if (r.name === flashCharId) item.classList.add('flash');

      const posClass = r.rank === 1 ? 'gold' : r.rank === 2 ? 'silver' : r.rank === 3 ? 'bronze' : 'other';
      const barPct = maxCount > 0 ? (r.count / maxCount * 100) : 0;

      item.innerHTML = `
        <div class="rank-pos ${posClass}">${r.rank}</div>
        <div class="rank-name">${r.name}</div>
        <div class="rank-bar-wrap"><div class="rank-bar" style="width:${barPct}%"></div></div>
        <div class="rank-count">${r.count}次</div>
      `;
      list.appendChild(item);
    });

    document.getElementById('rank-total').textContent = `${totalInteractions} 次互动`;
    document.getElementById('rank-chars').textContent = `角色总数: ${rankings.length}`;

    const lastHitEl = document.getElementById('rank-last-hit');
    if (lastHitTs) {
      const ago = Math.round((Date.now() - new Date(lastHitTs).getTime()) / 1000);
      lastHitEl.textContent = ago < 60 ? `${ago}s ago` : `${Math.round(ago / 60)}m ago`;
    } else {
      lastHitEl.textContent = '';
    }
  }

  /* ── Init ── */
  connectWS();
  syncUI();
  refreshList();
  renderRanking();
})();
