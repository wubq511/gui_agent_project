# gui_operator/execute.py
import pyautogui
import pyperclip
import mss
import time
import threading
import hashlib
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Optional, Callable, Tuple
from pathlib import Path


pyautogui.FAILSAFE = False


class ScreenshotOptimizer:
    """截图优化器 - 支持异步截图和缓存"""
    def __init__(self, cache_enabled: bool = True):
        self._cache_enabled = cache_enabled
        self._last_screenshot_hash: Optional[str] = None
        self._last_screenshot_time: float = 0
        self._screenshot_cache_duration: float = 0.1
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._pending_screenshot = None
    
    def take_screenshot_async(self, save_path: str) -> Future:
        """异步截图"""
        future = self._executor.submit(self._take_screenshot_sync, save_path)
        return future
    
    def _take_screenshot_sync(self, save_path: str) -> str:
        """同步截图"""
        with mss.mss() as sct:
            sct.shot(output=save_path)
        return save_path
    
    def should_take_new_screenshot(self) -> bool:
        """判断是否需要新截图（避免频繁截图）"""
        if not self._cache_enabled:
            return True
        current_time = time.time()
        return (current_time - self._last_screenshot_time) > self._screenshot_cache_duration


SCREENSHOT_OPTIMIZER = ScreenshotOptimizer()


class SmartWait:
    """智能等待 - 根据系统负载动态调整等待时间"""
    def __init__(self):
        self._last_operation_time = time.time()
        self._adaptive_delays = {
            "click": 0.3,
            "type": 0.3,
            "scroll": 0.3,
            "drag": 0.5,
            "hotkey": 0.3,
            "default": 0.5,
        }
        self._min_delay = 0.1
        self._max_delay = 2.0
    
    def get_adaptive_delay(self, operation: str) -> float:
        """获取自适应延迟时间"""
        base_delay = self._adaptive_delays.get(operation, self._adaptive_delays["default"])
        time_since_last = time.time() - self._last_operation_time
        
        if time_since_last < 0.5:
            adjusted_delay = base_delay * 0.5
        elif time_since_last > 2.0:
            adjusted_delay = base_delay * 1.5
        else:
            adjusted_delay = base_delay
        
        return max(self._min_delay, min(adjusted_delay, self._max_delay))
    
    def record_operation(self):
        """记录操作时间"""
        self._last_operation_time = time.time()


SMART_WAIT = SmartWait()


class Operation:
    """GUI操作工具类（优化版）"""
    
    def __init__(self, use_smart_wait: bool = True):
        self.use_smart_wait = use_smart_wait
        self._sct = None
    
    def _get_sct(self):
        """延迟初始化 mss 实例"""
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct
    
    def click(self, x: int, y: int, adaptive_wait: bool = True):
        """点击指定坐标"""
        print(f"🖱️  点击坐标 ({x}, {y})")
        pyautogui.click(x=x, y=y)
        if adaptive_wait and self.use_smart_wait:
            delay = SMART_WAIT.get_adaptive_delay("click")
            time.sleep(delay)
            SMART_WAIT.record_operation()
    
    def input(self, text: str, adaptive_wait: bool = True):
        """输入文本（使用粘贴方式，支持中文）"""
        print(f"⌨️  输入: {text}")
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        if adaptive_wait and self.use_smart_wait:
            delay = SMART_WAIT.get_adaptive_delay("type")
            time.sleep(delay)
            SMART_WAIT.record_operation()
    
    def screenshot(self, save_path: str, use_async: bool = False) -> str:
        """截图并保存"""
        if use_async:
            future = SCREENSHOT_OPTIMIZER.take_screenshot_async(save_path)
            future.result()
        else:
            with mss.mss() as sct:
                sct.shot(output=save_path)
        print(f"📸 截图已保存: {save_path}")
        return save_path
    
    def screenshot_fast(self, save_path: str) -> str:
        """快速截图 - 复用 mss 实例"""
        sct = self._get_sct()
        sct.shot(output=save_path)
        print(f"📸 快速截图已保存: {save_path}")
        return save_path
    
    def hotkey(self, *keys, adaptive_wait: bool = True):
        """按下组合键"""
        print(f"⌨️  按下组合键: {' + '.join(keys)}")
        pyautogui.hotkey(*keys)
        if adaptive_wait and self.use_smart_wait:
            delay = SMART_WAIT.get_adaptive_delay("hotkey")
            time.sleep(delay)
            SMART_WAIT.record_operation()
    
    def wait(self, seconds: float = 1.0):
        """等待指定时间"""
        print(f"⏱️  等待 {seconds} 秒...")
        time.sleep(seconds)
    
    def wait_smart(self, operation: str = "default"):
        """智能等待 - 根据操作类型自动调整"""
        delay = SMART_WAIT.get_adaptive_delay(operation)
        print(f"⏱️  智能等待 {delay:.2f} 秒...")
        time.sleep(delay)
        SMART_WAIT.record_operation()
    
    def double_click(self, x: int, y: int, adaptive_wait: bool = True):
        """双击指定坐标"""
        print(f"🖱️🖱️ 双击坐标 ({x}, {y})")
        pyautogui.doubleClick(x=x, y=y)
        if adaptive_wait and self.use_smart_wait:
            delay = SMART_WAIT.get_adaptive_delay("click")
            time.sleep(delay)
            SMART_WAIT.record_operation()
    
    def scroll(self, x: int, y: int, direction: str, amount: int = 500):
        """滚动操作"""
        pyautogui.moveTo(x, y)
        scroll_amount = amount if direction in ["up", "right"] else -amount
        pyautogui.scroll(scroll_amount)
        print(f"📜 滚动: {direction} at ({x}, {y})，步长: {scroll_amount}")
        if self.use_smart_wait:
            delay = SMART_WAIT.get_adaptive_delay("scroll")
            time.sleep(delay)
            SMART_WAIT.record_operation()
    
    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5):
        """拖拽操作"""
        pyautogui.moveTo(x1, y1)
        pyautogui.drag(x2 - x1, y2 - y1, duration=duration)
        print(f"🎯 拖拽: ({x1}, {y1}) -> ({x2}, {y2})")
        if self.use_smart_wait:
            delay = SMART_WAIT.get_adaptive_delay("drag")
            time.sleep(delay)
            SMART_WAIT.record_operation()
    
    def close(self):
        """清理资源"""
        if self._sct is not None:
            self._sct.close()
            self._sct = None
