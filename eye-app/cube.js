/**
 * Cube — 3D Blob 角色 (Three.js)
 *
 * 原创 IP: 一个会呼吸的软体球，有眼睛、眉毛、嘴巴。
 * 每种情绪有独立的颜色、形变、五官参数，切换时平滑插值。
 *
 * 公开 API:
 *   CubeCharacter.init(container)   — 初始化场景
 *   CubeCharacter.setEmotion(name)  — 切换情绪
 *   CubeCharacter.destroy()         — 清理资源
 */
const CubeCharacter = (() => {
  // ─── 情绪参数 ───
  const EMOTIONS = {
    calm: {
      baseColor: [0.3, 0.5, 0.9], rimColor: [0.6, 0.8, 1.0],
      noise: 0.2, eyeScale: 1.0, eyeSpace: 0.42, browL: 0, browA: 0,
      mouthX: 0.4, mouthY: 0.02,
      pulseFreq: 1.2, pulseAmp: 0.02, jitter: 0, tilt: 0
    },
    happy: {
      baseColor: [0.9, 0.4, 0.7], rimColor: [1.0, 0.8, 0.9],
      noise: 0.35, eyeScale: 0.45, eyeSpace: 0.45, browL: 0.15, browA: -0.2,
      mouthX: 0.8, mouthY: 0.15,
      pulseFreq: 3.5, pulseAmp: 0.06, jitter: 0, tilt: 0
    },
    excited: {
      baseColor: [1.0, 0.5, 0.2], rimColor: [1.0, 0.9, 0.4],
      noise: 0.6, eyeScale: 1.3, eyeSpace: 0.55, browL: 0.25, browA: 0.3,
      mouthX: 0.5, mouthY: 0.5,
      pulseFreq: 8.0, pulseAmp: 0.12, jitter: 0.02, tilt: 0
    },
    curious: {
      baseColor: [0.2, 0.8, 0.6], rimColor: [0.7, 1.0, 0.9],
      noise: 0.3, eyeScale: 1.1, eyeSpace: 0.42, browL: 0.1, browA: 0.2,
      mouthX: 0.3, mouthY: 0.05,
      pulseFreq: 2.0, pulseAmp: 0.03, jitter: 0, tilt: 0.2
    },
    sleepy: {
      baseColor: [0.3, 0.3, 0.4], rimColor: [0.5, 0.5, 0.6],
      noise: 0.1, eyeScale: 0.15, eyeSpace: 0.4, browL: -0.1, browA: 0,
      mouthX: 0.3, mouthY: 0.02,
      pulseFreq: 0.6, pulseAmp: 0.015, jitter: 0, tilt: -0.1
    },
    shy: {
      baseColor: [1.0, 0.7, 0.75], rimColor: [1.0, 0.9, 0.9],
      noise: 0.2, eyeScale: 0.8, eyeSpace: 0.35, browL: 0.05, browA: -0.1,
      mouthX: 0.2, mouthY: 0.02,
      pulseFreq: 4.0, pulseAmp: 0.02, jitter: 0.01, tilt: 0
    },
    grumpy: {
      baseColor: [0.6, 0.1, 0.2], rimColor: [0.9, 0.2, 0.3],
      noise: 0.8, eyeScale: 0.8, eyeSpace: 0.5, browL: 0, browA: 0.4,
      mouthX: 0.6, mouthY: 0.05,
      pulseFreq: 10.0, pulseAmp: 0.01, jitter: 0.05, tilt: 0
    }
  };

  // ─── Shader 源码 ───
  const VERT = `
    varying vec3 vNormal;
    varying vec3 vPosition;
    varying float vNoise;
    uniform float uTime;
    uniform float uNoiseIntensity;

    vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
    vec4 mod289(vec4 x){return x-floor(x*(1.0/289.0))*289.0;}
    vec4 permute(vec4 x){return mod289(((x*34.0)+1.0)*x);}
    vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
    float snoise(vec3 v){
      const vec2 C=vec2(1.0/6.0,1.0/3.0);
      const vec4 D=vec4(0.0,0.5,1.0,2.0);
      vec3 i=floor(v+dot(v,C.yyy));
      vec3 x0=v-i+dot(i,C.xxx);
      vec3 g=step(x0.yzx,x0.xyz);
      vec3 l=1.0-g;
      vec3 i1=min(g.xyz,l.zxy);
      vec3 i2=max(g.xyz,l.zxy);
      vec3 x1=x0-i1+C.xxx;
      vec3 x2=x0-i2+C.yyy;
      vec3 x3=x0-D.yyy;
      i=mod289(i);
      vec4 p=permute(permute(permute(
        i.z+vec4(0.0,i1.z,i2.z,1.0))
        +i.y+vec4(0.0,i1.y,i2.y,1.0))
        +i.x+vec4(0.0,i1.x,i2.x,1.0));
      float n_=0.142857142857;
      vec3 ns=n_*D.wyz-D.xzx;
      vec4 j=p-49.0*floor(p*ns.z*ns.z);
      vec4 x_=floor(j*ns.z);
      vec4 y_=floor(j-7.0*x_);
      vec4 x=x_*ns.x+ns.yyyy;
      vec4 y=y_*ns.x+ns.yyyy;
      vec4 h=1.0-abs(x)-abs(y);
      vec4 b0=vec4(x.xy,y.xy);
      vec4 b1=vec4(x.zw,y.zw);
      vec4 s0=floor(b0)*2.0+1.0;
      vec4 s1=floor(b1)*2.0+1.0;
      vec4 sh=-step(h,vec4(0.0));
      vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;
      vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
      vec3 p0=vec3(a0.xy,h.x);
      vec3 p1=vec3(a0.zw,h.y);
      vec3 p2=vec3(a1.xy,h.z);
      vec3 p3=vec3(a1.zw,h.w);
      vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
      p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
      vec4 m=max(0.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0);
      m=m*m;
      return 42.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
    }

    void main(){
      vNormal=normalize(normalMatrix*normal);
      float noise=snoise(vec3(position.xy*0.45,uTime*0.4));
      vNoise=noise;
      vec3 newPos=position+normal*(noise*uNoiseIntensity);
      vPosition=newPos;
      gl_Position=projectionMatrix*modelViewMatrix*vec4(newPos,1.0);
    }
  `;

  const FRAG = `
    varying vec3 vNormal;
    varying vec3 vPosition;
    varying float vNoise;
    uniform float uTime;
    uniform vec3 uBaseColor;
    uniform vec3 uRimColor;

    void main(){
      vec3 normal=normalize(vNormal);
      vec3 viewDir=normalize(vec3(0.0,0.0,1.0));
      float fresnel=pow(1.0-dot(normal,viewDir),2.5);
      vec3 finalColor=mix(uBaseColor,uRimColor,fresnel);
      float spec=pow(max(dot(normal,viewDir),0.0),64.0);
      finalColor+=spec*0.4;
      gl_FragColor=vec4(finalColor,1.0);
    }
  `;

  // ─── 场景对象 ───
  let scene, camera, renderer, blob, material;
  let eyes = [], brows = [], mouth;
  let clock;
  let targetEmotion = 'calm';
  let animId = null;
  const LERP = 0.12;

  let state = {
    noise: 0.2, eyeScale: 1, eyeSpace: 0.42,
    browL: 0, browA: 0, mouthX: 0.4, mouthY: 0.02,
    tilt: 0, jitter: 0
  };

  function init(container) {
    clock = new THREE.Clock();
    scene = new THREE.Scene();

    camera = new THREE.PerspectiveCamera(60, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.z = 6;

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // 身体
    const geometry = new THREE.SphereGeometry(1.8, 128, 128);
    material = new THREE.ShaderMaterial({
      vertexShader: VERT,
      fragmentShader: FRAG,
      uniforms: {
        uTime: { value: 0 },
        uNoiseIntensity: { value: 0.2 },
        uBaseColor: { value: new THREE.Color(0.3, 0.5, 0.9) },
        uRimColor: { value: new THREE.Color(0.6, 0.8, 1.0) }
      }
    });
    blob = new THREE.Mesh(geometry, material);
    scene.add(blob);

    // 五官材质
    const faceMat = new THREE.MeshPhongMaterial({ color: 0x111111, shininess: 100, depthTest: false });

    // 眼睛
    const eyeGeo = new THREE.SphereGeometry(0.12, 32, 32);
    for (let i = 0; i < 2; i++) {
      const p = new THREE.Group();
      const m = new THREE.Mesh(eyeGeo, faceMat);
      m.renderOrder = 999;
      const dot = new THREE.Mesh(
        new THREE.SphereGeometry(0.04, 12, 12),
        new THREE.MeshBasicMaterial({ color: 0xffffff })
      );
      dot.position.set(0.04, 0.04, 0.09);
      m.add(dot);
      p.add(m);
      scene.add(p);
      eyes.push({ p, m });
    }

    // 眉毛
    const browGeo = new THREE.BoxGeometry(0.2, 0.02, 0.05);
    for (let i = 0; i < 2; i++) {
      const m = new THREE.Mesh(browGeo, faceMat);
      m.renderOrder = 1000;
      scene.add(m);
      brows.push(m);
    }

    // 嘴巴
    mouth = new THREE.Mesh(new THREE.SphereGeometry(0.12, 32, 32), faceMat);
    mouth.renderOrder = 1000;
    scene.add(mouth);

    // 响应式
    window.addEventListener('resize', () => {
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    });

    animate();
  }

  function animate() {
    animId = requestAnimationFrame(animate);
    const time = clock.getElapsedTime();
    const cfg = EMOTIONS[targetEmotion] || EMOTIONS.calm;

    // 插值所有参数
    state.noise = THREE.MathUtils.lerp(state.noise, cfg.noise, LERP);
    state.eyeScale = THREE.MathUtils.lerp(state.eyeScale, cfg.eyeScale, LERP);
    state.eyeSpace = THREE.MathUtils.lerp(state.eyeSpace, cfg.eyeSpace, LERP);
    state.browL = THREE.MathUtils.lerp(state.browL, cfg.browL, LERP);
    state.browA = THREE.MathUtils.lerp(state.browA, cfg.browA, LERP);
    state.mouthX = THREE.MathUtils.lerp(state.mouthX, cfg.mouthX, LERP);
    state.mouthY = THREE.MathUtils.lerp(state.mouthY, cfg.mouthY, LERP);
    state.tilt = THREE.MathUtils.lerp(state.tilt, cfg.tilt, LERP);
    state.jitter = THREE.MathUtils.lerp(state.jitter, cfg.jitter, LERP);

    material.uniforms.uBaseColor.value.lerp(new THREE.Color(...cfg.baseColor), 0.05);
    material.uniforms.uRimColor.value.lerp(new THREE.Color(...cfg.rimColor), 0.05);
    material.uniforms.uNoiseIntensity.value = state.noise;
    material.uniforms.uTime.value = time;

    // 身体动画
    const pulse = 1.0 + Math.sin(time * cfg.pulseFreq) * cfg.pulseAmp;
    blob.scale.set(pulse, pulse, pulse);
    blob.position.y = Math.sin(time * 0.5) * 0.1;
    blob.rotation.z = THREE.MathUtils.lerp(blob.rotation.z, state.tilt, 0.1);

    // 五官定位
    const faceY = blob.position.y + 0.2;
    const jitterX = (Math.random() - 0.5) * state.jitter;
    const jitterY = (Math.random() - 0.5) * state.jitter;
    const lookX = Math.sin(time * 0.4) * 0.1 + jitterX;
    const lookY = Math.cos(time * 0.3) * 0.08 + jitterY;

    // 眼睛
    eyes.forEach((eye, i) => {
      const side = i === 0 ? -1 : 1;
      eye.p.position.set(side * state.eyeSpace + lookX, faceY + lookY, 1.95);
      eye.p.lookAt(camera.position);
      const blink = (time % 4 < 0.15) ? 0.1 : 1.0;
      eye.m.scale.set(1, state.eyeScale * blink, 1);
    });

    // 眉毛
    brows.forEach((brow, i) => {
      const side = i === 0 ? -1 : 1;
      brow.position.set(side * state.eyeSpace + lookX * 0.7, faceY + 0.25 + state.browL + lookY, 1.98);
      brow.rotation.z = state.browA * side;
    });

    // 嘴巴
    mouth.position.set(lookX * 0.5, faceY - 0.4 + lookY, 1.98);
    mouth.scale.set(state.mouthX, state.mouthY, 0.1);

    renderer.render(scene, camera);
  }

  function setEmotion(emotion) {
    if (EMOTIONS[emotion]) {
      targetEmotion = emotion;
    }
  }

  function destroy() {
    if (animId) cancelAnimationFrame(animId);
    if (renderer) renderer.dispose();
  }

  return { init, setEmotion, destroy };
})();
