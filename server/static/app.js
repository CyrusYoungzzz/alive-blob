/** Mobile control panel — photo upload, emotion control, character management */
(() => {
  const API = '';
  const ENGINE_WS = `ws://${location.hostname}:8000/ws/mobile`;
  let ws = null;
  let currentCharacter = null;
  let currentEmotion = 'calm';

  // Tab switching
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`page-${tab.dataset.tab}`).classList.add('active');
      if (tab.dataset.tab === 'upload') refreshCharacterList();
    });
  });

  // WebSocket connection to Engine
  function connectWS() {
    ws = new WebSocket(ENGINE_WS);
    ws.onopen = () => console.log('[Mobile WS] Connected');
    ws.onclose = () => {
      console.log('[Mobile WS] Disconnected, reconnecting...');
      setTimeout(connectWS, 2000);
    };
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'state_sync') {
        currentEmotion = data.emotion;
        currentCharacter = data.character;
        updateHomeStatus(data);
        updateEmotionGrid();
      }
    };
    ws.onerror = () => ws.close();
  }

  function sendWS(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    }
  }

  // Home status
  function updateHomeStatus(state) {
    document.getElementById('s-character').textContent = state.character || '--';
    document.getElementById('s-emotion').textContent = state.emotion || '--';
    const img = document.getElementById('preview-img');
    if (state.character && state.emotion) {
      img.src = `${API}/characters/${state.character}/${state.emotion}.png`;
      img.style.display = 'block';
    } else {
      img.style.display = 'none';
    }
  }

  // Emotion control
  const EMOTIONS = [
    { id: 'calm', label: '😌 平静' },
    { id: 'happy', label: '😄 开心' },
    { id: 'excited', label: '🤩 兴奋' },
    { id: 'curious', label: '🤔 好奇' },
    { id: 'sleepy', label: '😴 困倦' },
    { id: 'shy', label: '😳 害羞' },
    { id: 'grumpy', label: '😤 不爽' },
  ];

  const emotionGrid = document.getElementById('emotion-grid');
  EMOTIONS.forEach(em => {
    const btn = document.createElement('button');
    btn.className = 'emotion-btn';
    btn.dataset.emotion = em.id;
    btn.textContent = em.label;
    btn.addEventListener('click', () => {
      sendWS({ type: 'set_emotion', emotion: em.id });
    });
    emotionGrid.appendChild(btn);
  });

  function updateEmotionGrid() {
    document.querySelectorAll('.emotion-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.emotion === currentEmotion);
    });
  }

  // Photo upload
  const photoInput = document.getElementById('photo-input');
  const photoPreview = document.getElementById('photo-preview');
  const previewContainer = document.getElementById('photo-preview-container');
  const charNameInput = document.getElementById('char-name');
  const btnCreate = document.getElementById('btn-create');
  const uploadStatus = document.getElementById('upload-status');

  photoInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      photoPreview.src = ev.target.result;
      previewContainer.style.display = 'block';
      checkCreateReady();
    };
    reader.readAsDataURL(file);
  });

  charNameInput.addEventListener('input', checkCreateReady);

  function checkCreateReady() {
    btnCreate.disabled = !(charNameInput.value.trim() && photoInput.files.length);
  }

  btnCreate.addEventListener('click', async () => {
    const name = charNameInput.value.trim();
    const file = photoInput.files[0];
    if (!name || !file) return;

    btnCreate.disabled = true;
    uploadStatus.textContent = '⏳ 上传中...';

    const formData = new FormData();
    formData.append('name', name);
    formData.append('photo', file);

    try {
      const resp = await fetch(`${API}/api/characters`, { method: 'POST', body: formData });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || resp.statusText);
      }
      uploadStatus.textContent = '🎨 AI 正在生成表情包...';

      await pollCharacterReady(name);

      uploadStatus.textContent = '✅ 生成完成！';
      sendWS({ type: 'switch_character', name });
      refreshCharacterList();

      charNameInput.value = '';
      photoInput.value = '';
      previewContainer.style.display = 'none';
    } catch (err) {
      uploadStatus.textContent = `❌ ${err.message}`;
    }
    btnCreate.disabled = false;
  });

  async function pollCharacterReady(name, maxWait = 60000) {
    const start = Date.now();
    while (Date.now() - start < maxWait) {
      await new Promise(r => setTimeout(r, 1000));
      const resp = await fetch(`${API}/api/characters/${name}`);
      if (!resp.ok) continue;
      const data = await resp.json();
      if (data.status === 'ready') return;
      if (data.status.startsWith('error')) throw new Error(data.status);
    }
    throw new Error('生成超时');
  }

  // Character list
  const characterList = document.getElementById('character-list');

  async function refreshCharacterList() {
    try {
      const resp = await fetch(`${API}/api/characters`);
      const chars = await resp.json();
      characterList.innerHTML = '';
      chars.forEach(c => {
        const card = document.createElement('div');
        card.className = 'char-card';
        card.innerHTML = `
          <div>
            <div class="name">${c.display_name || c.name}</div>
            <div class="status">${c.emotions_ready}/${c.emotions_total} 表情 · ${c.status}</div>
          </div>
          <div>
            <button class="use-btn" data-name="${c.name}">使用</button>
            <button class="del-btn" data-name="${c.name}">删除</button>
          </div>
        `;
        card.querySelector('.use-btn').addEventListener('click', () => {
          sendWS({ type: 'switch_character', name: c.name });
        });
        card.querySelector('.del-btn').addEventListener('click', async () => {
          if (!confirm(`确定删除 ${c.name}？`)) return;
          await fetch(`${API}/api/characters/${c.name}`, { method: 'DELETE' });
          refreshCharacterList();
        });
        characterList.appendChild(card);
      });
    } catch (err) {
      characterList.innerHTML = `<p style="color:#888">加载失败</p>`;
    }
  }

  // Init
  connectWS();
  refreshCharacterList();
})();
