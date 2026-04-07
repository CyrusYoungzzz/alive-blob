/**
 * 播放器 — 管理照片显示和情绪切换
 *
 * 消息类型:
 *   set_face    → 加载用户照片 (character 切换时)
 *   play_emotion → 切换 CSS 情绪特效 + 粒子
 */
(() => {
  const face = document.getElementById('face');
  const screen = document.getElementById('screen');
  const SERVER_BASE = `http://${location.hostname}:8080`;
  let currentEmotion = 'calm';

  function setFace(imageUrl) {
    const fullUrl = imageUrl.startsWith('http') ? imageUrl : SERVER_BASE + imageUrl;
    face.src = fullUrl;
  }

  function setEmotion(emotion) {
    currentEmotion = emotion;
    // 更新 screen class → 触发 CSS 滤镜 + 动画
    screen.className = `emotion-${emotion}`;
    // 更新粒子系统
    Particles.setEmotion(emotion);
  }

  // 监听 Engine 消息
  EyeWS.onMessage = (data) => {
    if (data.type === 'set_face') {
      setFace(data.image_url);
    } else if (data.type === 'play_emotion') {
      // 兼容：如果带 image_path 且还没有 face，用它加载
      if (data.image_path && !face.src) {
        setFace(data.image_path);
      }
      setEmotion(data.emotion);
    }
  };

  // 启动
  EyeWS.connect();
  Particles.start();
  setEmotion('calm');
})();
