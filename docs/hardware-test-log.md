# 硬件测试记录

2026-04-06 实际接线与测试结果。

---

## 1. 继电器模块

**型号：** 4 路 5V 红板，TONGLING JOC-3FF-S-Z，支持高低电平触发

### 接线

**输入侧（信号）：**

| 端子 | 接到 | 说明 |
|------|------|------|
| DC+ | Pi 5V（针脚 2 或 4） | 继电器线圈供电 |
| DC- | Pi GND（针脚 6）→ 面包板 GND 总线 | 共地 |
| IN1 | Pi GPIO18（针脚 12） | 控制气泵 |
| IN2 | Pi GPIO23（针脚 16） | 控制左腿阀门 |
| IN3 | Pi GPIO24（针脚 18） | 控制右腿阀门 |
| IN4 | 不接 | 未使用 |

**输出侧（功率）：**

| 端子 | 接到 | 说明 |
|------|------|------|
| COM1、COM2、COM3 | 12V 电源适配器 +（通过面包板 + 轨并联） | 三路共用 12V+ |
| NO1 | 气泵正极 | 气泵负极接 GND 总线 |
| NO2 | 左腿电磁阀正极 | 阀门负极接 GND 总线 |
| NO3 | 右腿电磁阀正极 | 阀门负极接 GND 总线 |
| NC1-NC4 | 不接 | 使用常开模式，默认断电安全 |

**触发模式：** S1-S4 跳线帽设为 com 与 high 短接（高电平触发）

**12V 电源并联方式：** 12V+ 接面包板 + 轨，从 + 轨引三根线分别到 COM1、COM2、COM3。12V- 接面包板 - 轨（GND 总线）。

### 测试结果

- 继电器吸合/断开正常，有咔嗒声
- 气泵 + 阀门联动测试通过：先开阀门再开气泵，气流正常
- 阀门开关循环测试通过

**测试命令：**

```bash
# 单路继电器测试（GPIO18 = 气泵）
python3 -c "
from gpiozero import LED
import time
relay = LED(18)
relay.on()
time.sleep(10)
relay.off()
"

# 气泵 + 左阀联动测试
python3 -c "
from gpiozero import LED
import time
pump = LED(18)
valve_left = LED(23)
valve_left.on()
time.sleep(0.5)
pump.on()
time.sleep(10)
pump.off()
valve_left.off()
"

# 阀门开关循环测试（气泵持续，阀门开3秒关3秒x3）
python3 -c "
from gpiozero import LED
import time
pump = LED(18)
valve_left = LED(23)
pump.on()
time.sleep(0.5)
valve_left.on()
time.sleep(3)
valve_left.off()
time.sleep(3)
valve_left.on()
time.sleep(3)
valve_left.off()
time.sleep(3)
valve_left.on()
time.sleep(3)
valve_left.off()
pump.off()
"
```

---

## 2. MPR121 触摸传感器

### 接线

| MPR121 | Pi 针脚 | 说明 |
|--------|---------|------|
| VCC | 针脚 17（3.3V） | **必须 3.3V，接 5V 会烧** |
| GND | 面包板 GND 总线 | 共地 |
| SDA | 针脚 3（GPIO2） | I2C 数据 |
| SCL | 针脚 5（GPIO3） | I2C 时钟 |
| IRQ | 不接 | |
| ADDR | 不接 | 默认地址 0x5A |

### 启用 I2C

```bash
sudo raspi-config nonint do_i2c 0
```

### 安装驱动

```bash
sudo pip3 install --break-system-packages adafruit-circuitpython-mpr121
```

### 测试结果

I2C 检测成功，地址 0x5A：

```bash
sudo i2cdetect -y 1
```

**电容原始值读取：**

```bash
python3 -c "
import board
import busio
import adafruit_mpr121
i2c = busio.I2C(board.SCL, board.SDA)
mpr121 = adafruit_mpr121.MPR121(i2c)
import time
while True:
    values = [mpr121[i].raw_value for i in range(12)]
    print(values)
    time.sleep(0.5)
"
```

12 个数字对应通道 0-11 的电容值：

| 状态 | 通道 0 | 通道 1-11 |
|------|--------|----------|
| 正常（未触摸） | ~65 | 370-412（悬空底噪） |
| 触摸 | ~260 | 不变 |

触摸判定：数值变化超过 ~50 即可判定为触摸。

---

## 3. 网络配置

Pi 启动盘 `bootfs` 分区的 `network-config` 文件控制 WiFi 连接：

```yaml
network:
  version: 2
  wifis:
    wlan0:
      dhcp4: true
      regulatory-domain: "CN"
      access-points:
        "WiFi名":
          password: "密码"
```

SSH 启用：在 `bootfs` 分区根目录创建空的 `ssh` 文件。

**Pi SSH 登录：** `ssh cyrus@<Pi的IP>`
