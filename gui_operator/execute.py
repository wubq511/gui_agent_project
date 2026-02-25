# gui_operator/execute.py
import os
import pyautogui
import pyperclip
import mss
import time

# 允许鼠标移动到屏幕角落（默认会触发安全中断，此处禁用）
pyautogui.FAILSAFE = False

# 通过环境变量控制整体等待速度，便于在不同机器上调优性能：
# - GUI_AGENT_SPEED=0.5  表示整体等待时间减半；
# - GUI_AGENT_SPEED=1.0  表示保持原样；
# - GUI_AGENT_SPEED=2.0  表示整体等待时间翻倍（更稳但更慢）。
try:
    SPEED_MULTIPLIER = float(os.getenv("GUI_AGENT_SPEED", "1.0"))
except ValueError:
    SPEED_MULTIPLIER = 1.0


class Operation:
    """GUI操作工具类"""

    def click(self, x: int, y: int):
        """点击指定坐标"""
        print(f"🖱️  点击坐标 ({x}, {y})")
        pyautogui.click(x=x, y=y)

    def input(self, text: str):
        """输入文本（使用粘贴方式，支持中文）"""
        print(f"⌨️  输入: {text}")
        pyperclip.copy(text)  # 复制到剪贴板
        # 根据您的操作系统选择：Mac用'command'，Windows用'ctrl'
        pyautogui.hotkey("ctrl", "v")  # 如果是Windows，请改为 ('ctrl', 'v')

    def screenshot(self, save_path: str):
        """截图并保存"""
        with mss.mss() as sct:
            sct.shot(output=save_path)
        print(f"📸 截图已保存: {save_path}")

    def hotkey(self, *keys):
        """按下组合键（如ctrl+c）"""
        print(f"⌨️  按下组合键: {' + '.join(keys)}")
        pyautogui.hotkey(*keys)

    def wait(self, seconds: float = 1.0):
        """等待指定时间（支持全局加速/减速）"""
        effective = max(0.05, seconds * SPEED_MULTIPLIER)
        print(f"⏱️  等待 {effective} 秒（原始 {seconds} 秒）...")
        time.sleep(effective)

    def double_click(self, x: int, y: int):
        """双击指定坐标（文章代码中用到，这里补充）"""
        print(f"🖱️🖱️ 双击坐标 ({x}, {y})")
        pyautogui.doubleClick(x=x, y=y)
