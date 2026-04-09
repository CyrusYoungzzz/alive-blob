# 互动排名系统设计

> 日期：2026-04-09
> 状态：已确认

## 概述

在 Mobile 控制面板首页新增**角色互动排名**功能。页面改为 PC 展示用的左右分栏布局：左侧展示角色动画，右侧展示实时排行榜。互动计数仅来源于 MPR121 电容传感器的物理击打，计数绑定当前活跃角色，数据持久化到 JSON 文件。

## 需求

1. 统计系统中所有角色数量
2. 每个角色维护一个互动计数器
3. 互动来源：MPR121 电容传感器的物理击打（delta > 40）
4. 计数绑定当前活跃角色 — 谁在屏幕上，��打就算谁的
5. 根据互动计数实时排名
6. 在 Mobile/PC 首页左右分栏展示

## 页面布局

PC 展示用的左右分栏：

```
┌─────────────────────────────────────────────────────┐
│                    Alive Blob                       │
├────────────────────────┬────────────────────────���───┤
│                        │  排行榜                     │
│                        │                            │
│    [角色动画区域]       │  #1  科技薯    ████ 42次    │
│    (Eye App iframe)    │  #2  Cube      ███  28次    │
│    480×480 圆形裁切     │  #3  6         ██   15次    │
│                        │                            │
│                        │  角色总数: 3                 │
│                        │                            │
│   当前情绪: Happy      │  总互动: 85次               │
│   [情绪芯片按钮行]      │  最近一击: 2s ago           │
├────────────────────────┴────────────────────────────┤
│                  连接状态指示                         │
└─────────────────────────────────────────────────────┘
```

### 左侧 — 角色动画区

- Eye App iframe（圆形裁切，展示 3D Cube 或图片角色 + 情绪特效 + 粒子）
- 当前情绪标签
- 7 个情绪芯片按钮（保留现有功能）

### 右侧 — 排行榜

- 排名列表：排名序号 + 角色名 + 进度条 + 互动次数
- 当前活跃角色高亮显示
- 角色总数统计
- 总互动次数
- 最近一击时间（相对时间，如 "2s ago"）

## 数据流

```
MPR121 传感器 (I2C, 20ms 轮询)
  │  delta > 40 → 击打事件
  ▼
blob-engine/touch_sensor.py (新增)
  │  分类: light(40-100), medium(100-200), heavy(200+)
  ▼
blob-engine/engine.py
  │  1. interaction_counts[current_character] += 1
  │  2. 持久化到 data/interactions.json（防抖，最多每秒一次）
  │  3. 计算排名
  │  4. 广播 interaction_update 给所有 mobile 客户端
  ▼
Mobile/PC 客户端
  │  更新排行榜 UI
  ▼
排行榜实时刷新
```

**关键：事件驱动**，不轮询。只在击打发生时才推送更新，state_sync 不携带互��数据。

## 数据存储

文件路径：`data/interactions.json`

```json
{
  "counts": {
    "cube": 42,
    "keji-shu": 17,
    "6": 8
  },
  "last_hit_ts": "2026-04-09T06:30:00"
}
```

- 启动时加载历史数据，文件不存在则初始化空计数
- 每次互动后写入（防抖：最多每秒一次 I/O）
- 重启后数据不丢失

## WebSocket 协议扩展

### Engine → Mobile：互动更新（击打时推送）

```json
{
  "type": "interaction_update",
  "character": "cube",
  "count": 43,
  "rankings": [
    {"name": "cube", "count": 43, "rank": 1},
    {"name": "keji-shu", "count": 17, "rank": 2},
    {"name": "6", "count": 8, "rank": 3}
  ],
  "total": 68,
  "last_hit_ts": "2026-04-09T06:30:00"
}
```

### Engine → Mobile：初始化（连接时发送一次）

```json
{
  "type": "interaction_init",
  "rankings": [
    {"name": "cube", "count": 42, "rank": 1},
    {"name": "keji-shu", "count": 17, "rank": 2},
    {"name": "6", "count": 8, "rank": 3}
  ],
  "total": 67
}
```

不新增 Mobile → Engine 的消息类型，互动完全由传感器驱动。

## 新增/修改文件

| 文件 | 操作 | 职责 |
|------|------|------|
| `blob-engine/touch_sensor.py` | 新增 | MPR121 传感器读取，击打检测，回调通知 engine |
| `blob-engine/engine.py` | 修改 | 互动计数器、JSON 持久化、interaction_update/init 广播 |
| `server/static/app.js` | 修改 | 首页改为左右分栏，新增排行榜 UI |
| `server/static/index.html` | 修改 | 布局结构调整为左右分栏 |
| `data/interactions.json` | 新增（运行时生成） | 互动计数持久化存储 |

## touch_sensor.py 设计

从 `scripts/whip-test.py` 提取传感器读取逻辑：

- 独立线程运行，20ms 轮询 MPR121
- 基线自适应（指数移动平均）
- 击打分类：light / medium / heavy
- 通过回调函数通知 engine（`on_hit(intensity)`）
- Mac/非 Pi 环境提供 MockTouchSensor（日志输出，不阻塞）

## 排名计算

简单规则：按互动次数降序排列。次数相同则按角色名字母序。

```python
rankings = sorted(
    counts.items(),
    key=lambda x: (-x[1], x[0])
)
```
