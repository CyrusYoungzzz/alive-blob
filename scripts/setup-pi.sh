#!/usr/bin/env bash
# Alive Blob — Pi 一键环境配置脚本
# 用法: ssh 到 Pi 后执行  bash setup-pi.sh
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Alive Blob — Pi 环境配置"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

# ─── 1. 系统包 ───
echo ""
echo "[1/6] 安装系统依赖..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
  python3-venv python3-pip python3-dev \
  chromium \
  i2c-tools \
  libopenjp2-7 libtiff6 libatlas3-base \
  curl git

# ─── 2. 启用 I2C（MPR121 触摸传感器需要）───
echo ""
echo "[2/6] 启用 I2C..."
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null; then
  CONFIG_FILE="/boot/config.txt"
  [ -f /boot/firmware/config.txt ] && CONFIG_FILE="/boot/firmware/config.txt"
  echo "dtparam=i2c_arm=on" | sudo tee -a "$CONFIG_FILE" > /dev/null
  echo "  ✅ I2C 已启用（重启后生效）"
else
  echo "  ✅ I2C 已经启用"
fi

# 确保 i2c 模块开机加载
if ! grep -q "i2c-dev" /etc/modules 2>/dev/null; then
  echo "i2c-dev" | sudo tee -a /etc/modules > /dev/null
fi

# ─── 3. 圆屏 HDMI 配置（480x480）───
echo ""
echo "[3/6] 配置圆屏 HDMI 输出 (480x480)..."
CONFIG_FILE="/boot/config.txt"
[ -f /boot/firmware/config.txt ] && CONFIG_FILE="/boot/firmware/config.txt"

# 检查是否已配置
if grep -q "hdmi_cvt=480 480" "$CONFIG_FILE" 2>/dev/null; then
  echo "  ✅ 圆屏已配置"
else
  sudo tee -a "$CONFIG_FILE" > /dev/null << 'HDMI'

# ─── Alive Blob 圆屏配置 ───
hdmi_group=2
hdmi_mode=87
hdmi_cvt=480 480 60 1 0 0 0
hdmi_drive=2
# 如果屏幕不亮，取消下面���注释：
# hdmi_force_hotplug=1
HDMI
  echo "  ✅ 圆屏 HDMI 配置已写入（重启后生效）"
fi

# ─── 4. Python 虚拟环境 + 依赖 ───
echo ""
echo "[4/6] 安装 Python 依赖..."
if [ ! -d "$ROOT_DIR/.venv" ]; then
  python3 -m venv "$ROOT_DIR/.venv"
fi
source "$ROOT_DIR/.venv/bin/activate"
pip install -q --upgrade pip
pip install -q -r "$ROOT_DIR/server/requirements.txt" -r "$ROOT_DIR/blob-engine/requirements.txt"
# GPIO 和触摸传感器库（Pi 专用）
pip install -q RPi.GPIO adafruit-circuitpython-mpr121
echo "  ✅ Python 依赖安装完成"

# ─── 5. 创建 symlink（blob-engine → blob_engine）───
echo ""
echo "[5/6] 配置项目..."
if [ ! -e "$ROOT_DIR/blob_engine" ]; then
  ln -s "$ROOT_DIR/blob-engine" "$ROOT_DIR/blob_engine"
fi
mkdir -p "$ROOT_DIR/characters"
echo "  ✅ 项目目录就绪"

# ─── 6. 开机自启（可选）───
echo ""
echo "[6/6] 配置开机自启..."
SERVICE_FILE="/etc/systemd/system/alive-blob.service"
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Alive Blob
After=network.target

[Service]
Type=forking
User=$(whoami)
WorkingDirectory=$ROOT_DIR
ExecStart=/bin/bash $ROOT_DIR/scripts/start.sh
ExecStop=/bin/bash -c 'kill \$(cat /tmp/alive-blob-*.pid 2>/dev/null) 2>/dev/null; true'
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable alive-blob.service
echo "  ✅ 开机自启已配置 (alive-blob.service)"
echo "     手动控制: sudo systemctl start/stop/restart alive-blob"

# ─── 完成 ───
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ 配置完成！"
echo ""
echo "  下一步："
echo "  1. sudo reboot          (使 I2C 和圆屏配置生效)"
echo "  2. 重启后测试："
echo "     bash scripts/start.sh"
echo ""
echo "  验证硬件："
echo "     i2cdetect -y 1       (应看到 0x5A = MPR121)"
echo "     pinout                (查看 GPIO 引脚图)"
echo ""
echo "  手机访问："
PI_IP=$(hostname -I | awk '{print $1}')
echo "     http://${PI_IP}:8080"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
