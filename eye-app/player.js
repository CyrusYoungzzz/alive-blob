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
  let currentEmotion = 'sleepy';
  let cubeReady = false;
  let isCustomChar = false;

  function initCube() {
    CubeCharacter.init(container);
    cubeReady = true;
  }

  function showMode(mode) {
    currentMode = mode;
    if (mode === '3d') {
      container.style.display = '';
      face.classList.remove('active');
      if (!cubeReady) initCube();
      CubeCharacter.setEmotion(currentEmotion);
    } else {
      container.style.display = 'none';
      face.classList.add('active');
      // Only show particles for built-in image chars, not AIGC custom chars
      if (isCustomChar) {
        Particles.stop();
      } else {
        Particles.start();
        Particles.setEmotion(currentEmotion);
      }
      applyImageEmotion(currentEmotion);
    }
  }

  function applyImageEmotion(emotion) {
    screen.className = screen.className.replace(/\bemo-\w+/g, '').trim();
    screen.classList.add(`emo-${emotion}`);
  }

  function setEmotion(emotion, imagePath) {
    currentEmotion = emotion;
    if (isCustomChar && imagePath) {
      // Custom character: show AIGC-generated emotion PNG
      const url = imagePath.startsWith('http') ? imagePath : SERVER_BASE + imagePath;
      face.src = url;
      showMode('image');
    } else if (currentMode === '3d') {
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
        isCustomChar = false;
        CubeCharacter.clearTexture();
        CubeCharacter.showFace(true);
        Particles.stop();
        showMode('3d');
      } else if (charType === 'custom') {
        // Custom character: show AIGC emotion images in 2D mode
        isCustomChar = true;
        showMode('image');
      } else {
        // Built-in image character: 2D mode
        isCustomChar = false;
        const url = data.avatar || (data.image_url
          ? (data.image_url.startsWith('http') ? data.image_url : SERVER_BASE + data.image_url)
          : '');
        if (url) face.src = url;
        showMode('image');
      }
    } else if (data.type === 'play_emotion') {
      setEmotion(data.emotion, data.image_path);
    }
  };

  // Boot
  initCube();
  EyeWS.connect();
  setEmotion('sleepy');
})();
