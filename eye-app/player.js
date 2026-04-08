/**
 * Player — bridges WebSocket messages to Cube 3D / Image character display.
 *
 * Messages:
 *   set_face      → switch character (3d / image / custom)
 *   play_emotion  → change emotion effects
 */
(() => {
  const screen = document.getElementById('screen');
  const container = document.getElementById('container');
  const face = document.getElementById('face');
  const SERVER_BASE = `http://${location.hostname}:8080`;

  let currentMode = '3d';   // '3d' | 'image'
  let currentEmotion = 'calm';
  let cubeReady = false;

  function initCube() {
    CubeCharacter.init(container);
    cubeReady = true;
  }

  function showMode(mode) {
    currentMode = mode;
    if (mode === '3d') {
      container.style.display = '';
      face.classList.remove('active');
      Particles.stop();
      if (!cubeReady) initCube();
      CubeCharacter.setEmotion(currentEmotion);
    } else {
      container.style.display = 'none';
      face.classList.add('active');
      Particles.start();
      Particles.setEmotion(currentEmotion);
      applyImageEmotion(currentEmotion);
    }
  }

  function applyImageEmotion(emotion) {
    // remove old emo-* classes, add new
    screen.className = screen.className.replace(/\bemo-\w+/g, '').trim();
    screen.classList.add(`emo-${emotion}`);
  }

  function setEmotion(emotion) {
    currentEmotion = emotion;
    if (currentMode === '3d') {
      CubeCharacter.setEmotion(emotion);
    } else {
      applyImageEmotion(emotion);
      Particles.setEmotion(emotion);
    }
  }

  // Listen to Engine
  EyeWS.onMessage = (data) => {
    if (data.type === 'set_face') {
      const charType = data.char_type || 'custom';
      if (charType === '3d') {
        showMode('3d');
      } else {
        // image or custom character
        const url = data.avatar || (data.image_url
          ? (data.image_url.startsWith('http') ? data.image_url : SERVER_BASE + data.image_url)
          : '');
        if (url) face.src = url;
        showMode('image');
      }
    } else if (data.type === 'play_emotion') {
      setEmotion(data.emotion);
    }
  };

  // Boot
  initCube();
  EyeWS.connect();
  setEmotion('calm');
})();
