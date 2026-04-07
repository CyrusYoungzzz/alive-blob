"""步态控制器测试 — 使用 Mock GPIO（Mac 上也能跑）。"""

import pytest
import asyncio
import time
import sys
import os

# 确保能导入 blob-engine 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "blob-engine"))

from gait_controller import GaitController


@pytest.mark.asyncio
async def test_gait_starts_and_stops():
    """测试步态控制器能正常启停。"""
    gait = GaitController()
    await gait.start()
    assert gait._running
    await asyncio.sleep(0.2)
    await gait.stop()
    assert not gait._running
    assert not gait.is_pump_on


@pytest.mark.asyncio
async def test_emotion_changes_gait():
    """切换情绪后步态参数更新。"""
    gait = GaitController()
    gait.set_emotion("excited")
    assert gait._current_emotion == "excited"
    gait.set_emotion("sleepy")
    assert gait._current_emotion == "sleepy"


@pytest.mark.asyncio
async def test_intensity_clamp():
    """强度值应被 clamp 到 0.0-1.0。"""
    gait = GaitController()
    gait.set_intensity(1.5)
    assert gait._intensity == 1.0
    gait.set_intensity(-0.3)
    assert gait._intensity == 0.0
    gait.set_intensity(0.6)
    assert gait._intensity == 0.6


@pytest.mark.asyncio
async def test_leg_states():
    """leg_states 返回两元素列表。"""
    gait = GaitController()
    states = gait.leg_states
    assert len(states) == 2
    assert all(isinstance(v, float) for v in states)


@pytest.mark.asyncio
async def test_pump_watchdog():
    """气泵看门狗：手动设置超时状态后检查应停泵。"""
    gait = GaitController()
    # 模拟气泵已运行超过限制
    gait._pump_on = True
    gait._pump_start_time = time.monotonic() - 31  # 31 秒前启动
    gait._check_pump_watchdog()
    assert not gait._pump_on  # 应该被自动切断


@pytest.mark.asyncio
async def test_cleanup_turns_everything_off():
    """cleanup 应关闭所有输出。"""
    gait = GaitController()
    gait._pump_on = True
    gait._left_open = True
    gait._right_open = True
    gait.cleanup()
    assert not gait._pump_on
    assert not gait._left_open
    assert not gait._right_open
