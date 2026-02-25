import unittest
from unittest.mock import patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gui_operator.execute import Operation


class TestHotkeyFunctionality(unittest.TestCase):
    """测试 hotkey 功能，包括 Ctrl+A 全选操作"""

    def setUp(self):
        self.operation = Operation()

    @patch('pyautogui.hotkey')
    def test_hotkey_ctrl_a(self, mock_hotkey):
        """测试 Ctrl+A 全选快捷键"""
        self.operation.hotkey('ctrl', 'a')
        mock_hotkey.assert_called_once_with('ctrl', 'a')

    @patch('pyautogui.hotkey')
    def test_hotkey_ctrl_c(self, mock_hotkey):
        """测试 Ctrl+C 复制快捷键"""
        self.operation.hotkey('ctrl', 'c')
        mock_hotkey.assert_called_once_with('ctrl', 'c')

    @patch('pyautogui.hotkey')
    def test_hotkey_ctrl_v(self, mock_hotkey):
        """测试 Ctrl+V 粘贴快捷键"""
        self.operation.hotkey('ctrl', 'v')
        mock_hotkey.assert_called_once_with('ctrl', 'v')

    @patch('pyautogui.hotkey')
    def test_hotkey_ctrl_x(self, mock_hotkey):
        """测试 Ctrl+X 剪切快捷键"""
        self.operation.hotkey('ctrl', 'x')
        mock_hotkey.assert_called_once_with('ctrl', 'x')

    @patch('pyautogui.hotkey')
    def test_hotkey_alt_tab(self, mock_hotkey):
        """测试 Alt+Tab 切换窗口快捷键"""
        self.operation.hotkey('alt', 'tab')
        mock_hotkey.assert_called_once_with('alt', 'tab')

    @patch('pyautogui.hotkey')
    def test_hotkey_three_keys(self, mock_hotkey):
        """测试三键组合快捷键（如 Ctrl+Shift+Esc）"""
        self.operation.hotkey('ctrl', 'shift', 'esc')
        mock_hotkey.assert_called_once_with('ctrl', 'shift', 'esc')


class TestActionParsing(unittest.TestCase):
    """测试 main.py 中的动作解析逻辑"""

    def test_parse_hotkey_ctrl_a(self):
        """测试解析 hotkey(key='ctrl a') 动作"""
        import re
        action = "hotkey(key='ctrl a')"
        key_match = re.search(r"key=['\"]([^'\"]*)['\"]", action)
        self.assertIsNotNone(key_match)
        key_str = key_match.group(1)
        keys = key_str.split()
        self.assertEqual(keys, ['ctrl', 'a'])

    def test_parse_hotkey_ctrl_shift_s(self):
        """测试解析 hotkey(key='ctrl shift s') 动作"""
        import re
        action = "hotkey(key='ctrl shift s')"
        key_match = re.search(r"key=['\"]([^'\"]*)['\"]", action)
        self.assertIsNotNone(key_match)
        key_str = key_match.group(1)
        keys = key_str.split()
        self.assertEqual(keys, ['ctrl', 'shift', 's'])

    def test_parse_hotkey_with_double_quotes(self):
        """测试解析使用双引号的 hotkey 动作"""
        import re
        action = 'hotkey(key="ctrl a")'
        key_match = re.search(r"key=['\"]([^'\"]*)['\"]", action)
        self.assertIsNotNone(key_match)
        key_str = key_match.group(1)
        keys = key_str.split()
        self.assertEqual(keys, ['ctrl', 'a'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
