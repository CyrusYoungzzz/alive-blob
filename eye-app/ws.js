/** WebSocket client — connects to Blob Engine */
const EyeWS = (() => {
  const ENGINE_URL = `ws://${location.hostname}:8000/ws/eye`;
  let ws = null;
  let onMessage = null;

  function connect() {
    ws = new WebSocket(ENGINE_URL);
    ws.onopen = () => {
      console.log('[WS] Connected to Engine');
      document.getElementById('status-dot').classList.add('connected');
    };
    ws.onclose = () => {
      console.log('[WS] Disconnected, reconnecting in 2s...');
      document.getElementById('status-dot').classList.remove('connected');
      setTimeout(connect, 2000);
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (onMessage) onMessage(data);
    };
    ws.onerror = () => ws.close();
  }

  return {
    connect,
    set onMessage(fn) { onMessage = fn; },
  };
})();
