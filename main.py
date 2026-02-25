#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI Agent 主程序（优化版）
"""
import re
import json
import pyautogui
import time
from datetime import datetime
from typing import TypedDict, Optional, Dict, Any
from pathlib import Path
from langgraph.graph import StateGraph, END
from dataclasses import dataclass, field

from gui_operator.execute import Operation
from utils.model import GeminiChat, Model, PERF_STATS
from utils.prompts import COMPUTER_USE_UITARS


@dataclass
class StepMetrics:
    """单步性能指标"""
    step_number: int
    screenshot_time: float = 0.0
    api_time: float = 0.0
    execute_time: float = 0.0
    total_time: float = 0.0
    action_type: str = ""


class PerformanceMonitor:
    """性能监控器"""
    def __init__(self):
        self.step_metrics: list[StepMetrics] = []
        self.start_time: float = 0
        self.current_step: Optional[StepMetrics] = None
    
    def start_task(self):
        self.start_time = time.time()
        self.step_metrics = []
    
    def start_step(self, step_number: int):
        self.current_step = StepMetrics(step_number=step_number)
    
    def record_screenshot(self, duration: float):
        if self.current_step:
            self.current_step.screenshot_time = duration
    
    def record_api(self, duration: float):
        if self.current_step:
            self.current_step.api_time = duration
    
    def record_execute(self, duration: float, action_type: str):
        if self.current_step:
            self.current_step.execute_time = duration
            self.current_step.action_type = action_type
    
    def end_step(self):
        if self.current_step:
            self.current_step.total_time = (
                self.current_step.screenshot_time +
                self.current_step.api_time +
                self.current_step.execute_time
            )
            self.step_metrics.append(self.current_step)
            self.current_step = None
    
    def get_summary(self) -> Dict[str, Any]:
        total_time = time.time() - self.start_time
        total_steps = len(self.step_metrics)
        
        if total_steps == 0:
            return {"total_time": total_time, "total_steps": 0}
        
        avg_screenshot = sum(m.screenshot_time for m in self.step_metrics) / total_steps
        avg_api = sum(m.api_time for m in self.step_metrics) / total_steps
        avg_execute = sum(m.execute_time for m in self.step_metrics) / total_steps
        avg_step = sum(m.total_time for m in self.step_metrics) / total_steps
        
        action_counts: Dict[str, int] = {}
        for m in self.step_metrics:
            action_counts[m.action_type] = action_counts.get(m.action_type, 0) + 1
        
        return {
            "total_time": total_time,
            "total_steps": total_steps,
            "avg_step_time": avg_step,
            "avg_screenshot_time": avg_screenshot,
            "avg_api_time": avg_api,
            "avg_execute_time": avg_execute,
            "action_distribution": action_counts,
        }
    
    def print_summary(self):
        summary = self.get_summary()
        print("\n" + "=" * 50)
        print("📊 性能统计报告")
        print("=" * 50)
        print(f"总执行时间: {summary['total_time']:.2f}秒")
        print(f"总步骤数: {summary['total_steps']}")
        if summary['total_steps'] > 0:
            print(f"平均每步耗时: {summary['avg_step_time']:.2f}秒")
            print(f"  - 平均截图耗时: {summary['avg_screenshot_time']:.3f}秒")
            print(f"  - 平均API耗时: {summary['avg_api_time']:.2f}秒")
            print(f"  - 平均执行耗时: {summary['avg_execute_time']:.3f}秒")
            print(f"动作分布: {summary['action_distribution']}")
        print("=" * 50)


PERF_MONITOR = PerformanceMonitor()


class AgentState(TypedDict):
    instruction: str
    screenshot_path: str
    step: int
    thought: str
    action: str
    finished: bool


class GUIAgent:
    """GUI自动化Agent（优化版）"""
    
    def __init__(
        self, 
        instruction: str, 
        model_name: str = Model.GEMINI_3_FLASH, 
        max_steps: int = 100,
        api_key: str | None = None,
        use_smart_wait: bool = True,
        max_history: int = 10,
    ):
        self.instruction = instruction
        self.operation = Operation(use_smart_wait=use_smart_wait)
        self.lvm_chat = GeminiChat(
            api_key=api_key,
            model=model_name,
            max_history=max_history,
        )
        self.max_steps = max_steps
        self.s_dir = Path("screenshots")
        self.s_dir.mkdir(exist_ok=True)
        self.screen_width, self.screen_height = pyautogui.size()
        print(f"🖥️  屏幕尺寸: {self.screen_width} x {self.screen_height}")
        print(f"⚡ 优化模式已启用: 智能等待={use_smart_wait}, 历史限制={max_history}")

    def normalize_coords(self, x: int, y: int) -> tuple[int, int]:
        """将归一化坐标(0-1000)转换为实际像素坐标"""
        actual_x = int(x / 1000.0 * self.screen_width)
        actual_y = int(y / 1000.0 * self.screen_height)
        print(f"    归一化坐标 ({x}, {y}) -> 实际坐标 ({actual_x}, {actual_y})")
        return actual_x, actual_y

    def take_screenshot(self, state: AgentState) -> AgentState:
        """步骤1: 截图并保存"""
        step = state.get("step", 0) + 1
        PERF_MONITOR.start_step(step)
        
        start_time = time.time()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = str(self.s_dir / f"step_{step}_{timestamp}.png")
        self.operation.screenshot(screenshot_path)
        screenshot_duration = time.time() - start_time
        PERF_MONITOR.record_screenshot(screenshot_duration)
        
        return {
            **state,
            "screenshot_path": screenshot_path,
            "step": step,
            "finished": False
        }

    def model_decide(self, state: AgentState) -> AgentState:
        """步骤2: 模型决策"""
        start_time = time.time()
        prompt = COMPUTER_USE_UITARS.format(instruction=state["instruction"])
        
        response = self.lvm_chat.get_multimodal_response(
            text=prompt,
            image_paths=state["screenshot_path"],
            use_history=True
        )
        api_duration = time.time() - start_time
        PERF_MONITOR.record_api(api_duration)
        
        print(f"\n📸 Step {state['step']} - 模型响应:\n{response}\n")
        
        try:
            result = json.loads(response)
            thought = result.get("Thought", "")
            action = result.get("Action", "")
        except json.JSONDecodeError:
            thought_match = re.search(r'"Thought":\s*"([^"]*)"', response)
            action_match = re.search(r'"Action":\s*"([^"]*)"', response)
            thought = thought_match.group(1) if thought_match else ""
            action = action_match.group(1) if action_match else ""
        
        return {
            **state,
            "thought": thought,
            "action": action
        }

    def execute_action(self, state: AgentState) -> AgentState:
        """步骤3: 解析并执行动作"""
        start_time = time.time()
        action = state["action"]
        action_type = "unknown"
        
        if not action:
            print("⚠️ 没有可执行的动作")
            action_type = "none"
            PERF_MONITOR.record_execute(time.time() - start_time, action_type)
            PERF_MONITOR.end_step()
            return {**state, "finished": True}
        
        if action.startswith("finished("):
            content_match = re.search(r"finished\(content='([^']*)'\)", action)
            content = content_match.group(1) if content_match else "任务完成"
            print(f"✅ 任务完成: {content}")
            action_type = "finished"
            PERF_MONITOR.record_execute(time.time() - start_time, action_type)
            PERF_MONITOR.end_step()
            return {**state, "finished": True}
        
        try:
            action_type = self._parse_and_execute(action)
        except Exception as e:
            print(f"❌ 执行动作失败: {e}")
            print(f"   动作: {action}")
        
        execute_duration = time.time() - start_time
        PERF_MONITOR.record_execute(execute_duration, action_type)
        PERF_MONITOR.end_step()
        
        return state

    def _parse_and_execute(self, action: str) -> str:
        """解析动作字符串并执行，返回动作类型"""
        print(f"🔧 执行动作: {action}")
        
        if action.startswith("click("):
            point_match = re.search(r"<point>(\d+)\s+(\d+)</point>", action)
            if point_match:
                x, y = int(point_match.group(1)), int(point_match.group(2))
                actual_x, actual_y = self.normalize_coords(x, y)
                self.operation.click(actual_x, actual_y)
            return "click"
        
        elif action.startswith("type("):
            content_match = re.search(r"content=['\"]([^'\"]*)['\"]", action)
            if content_match:
                text = content_match.group(1)
                text = (
                    text.replace(r"\\n", "\n")
                    .replace(r"\'", "'")
                    .replace(r'\"', '"')
                    .replace(r"\n", "\n")
                )
                self.operation.input(text)
            return "type"
        
        elif action.startswith("left_double("):
            point_match = re.search(r"<point>(\d+)\s+(\d+)</point>", action)
            if point_match:
                x, y = int(point_match.group(1)), int(point_match.group(2))
                actual_x, actual_y = self.normalize_coords(x, y)
                self.operation.double_click(actual_x, actual_y)
            return "double_click"
        
        elif action.startswith("hotkey("):
            key_match = re.search(r"key=['\"]([^'\"]*)['\"]", action)
            if key_match:
                key_str = key_match.group(1)
                keys = key_str.split()
                self.operation.hotkey(*keys)
            return "hotkey"
        
        elif action.startswith("wait()"):
            self.operation.wait(5)
            return "wait"
        
        elif action.startswith("scroll("):
            point_match = re.search(r"<point>(\d+)\s+(\d+)</point>", action)
            direction_match = re.search(r"direction=['\"](\w+)['\"]", action)
            if point_match and direction_match:
                x, y = int(point_match.group(1)), int(point_match.group(2))
                actual_x, actual_y = self.normalize_coords(x, y)
                direction = direction_match.group(1)
                pyautogui.moveTo(actual_x, actual_y)
                scroll_amount = 500 if direction in ["up", "right"] else -500
                pyautogui.scroll(scroll_amount)
                print(f"📜 滚动: {direction} at ({actual_x}, {actual_y})，步长: {scroll_amount}")
                self.operation.wait(0.3)
            return "scroll"
        
        elif action.startswith("drag("):
            points = re.findall(r"<point>(\d+)\s+(\d+)</point>", action)
            if len(points) >= 2:
                x1, y1 = int(points[0][0]), int(points[0][1])
                x2, y2 = int(points[1][0]), int(points[1][1])
                actual_x1, actual_y1 = self.normalize_coords(x1, y1)
                actual_x2, actual_y2 = self.normalize_coords(x2, y2)
                pyautogui.moveTo(actual_x1, actual_y1)
                pyautogui.drag(actual_x2 - actual_x1, actual_y2 - actual_y1, duration=0.5)
                print(f"🎯 拖拽: ({actual_x1}, {actual_y1}) -> ({actual_x2}, {actual_y2})")
                self.operation.wait(0.3)
            return "drag"
        
        else:
            print(f"⏸️  暂未实现的动作类型: {action.split('(')[0]}，程序将等待2秒。")
            self.operation.wait(2)
            return "unknown"

    def should_continue(self, state: AgentState) -> str:
        """判断是否继续循环"""
        if state.get("finished", False):
            return "end"
        if state.get("step", 0) >= self.max_steps:
            print(f"⏹️ 已达到最大步骤数 {self.max_steps}，自动结束本次任务。")
            return "end"
        return "continue"

    def run(self) -> Dict[str, Any]:
        """运行Agent"""
        PERF_MONITOR.start_task()
        
        workflow = StateGraph(AgentState)
        workflow.add_node("screenshot", self.take_screenshot)
        workflow.add_node("decide", self.model_decide)
        workflow.add_node("execute", self.execute_action)
        workflow.set_entry_point("screenshot")
        workflow.add_edge("screenshot", "decide")
        workflow.add_edge("decide", "execute")
        workflow.add_conditional_edges(
            "execute",
            self.should_continue,
            {"continue": "screenshot", "end": END}
        )
        
        app = workflow.compile()
        print(f"🚀 开始执行任务: {self.instruction}\n")
        
        config = {"recursion_limit": self.max_steps + 10}
        
        try:
            final_state = app.invoke(
                {"instruction": self.instruction, "step": 0},
                config=config
            )
            print(f"\n🎉 任务结束! 共执行 {final_state.get('step', 0)} 步")
        except Exception as e:
            print(f"\n⚠️ 任务执行异常: {e}")
            final_state = {"step": 0}
        
        PERF_MONITOR.print_summary()
        
        return PERF_MONITOR.get_summary()


if __name__ == "__main__":
    your_instruction = "我想买一个手机，帮我看看哪个手机性价比高"
    agent = GUIAgent(instruction=your_instruction)
    agent.run()
