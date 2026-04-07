/** Image player — dual layer crossfade */
(() => {
  const layerA = document.getElementById('layer-a');
  const layerB = document.getElementById('layer-b');
  const screen = document.getElementById('screen');
  let currentLayer = layerA;

  const SERVER_BASE = `http://${location.hostname}:8080`;

  function showEmotion(imagePath, emotion) {
    const nextLayer = currentLayer === layerA ? layerB : layerA;
    const fullUrl = SERVER_BASE + imagePath;

    nextLayer.onload = () => {
      currentLayer.classList.remove('active');
      nextLayer.classList.add('active');
      currentLayer = nextLayer;

      screen.className = '';
      screen.classList.add(`emotion-${emotion}`);
    };
    nextLayer.src = fullUrl;
  }

  EyeWS.onMessage = (data) => {
    if (data.type === 'play_emotion') {
      showEmotion(data.image_path, data.emotion);
    }
  };

  EyeWS.connect();
})();
