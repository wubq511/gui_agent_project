#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import json
import pyautogui
import time
from datetime import datetime
from typing import TypedDict
from pathlib import Path
from langgraph.graph import StateGraph, END

from gui_operator.execute import Operation
from utils.model import GeminiChat, Model
from utils.prompts import COMPUTER_USE_UITARS


class AgentState(TypedDict):
    instruction: str
    screenshot_path: str
    step: int
    thought: str
    action: str
    finished: bool


class GUIAgent:
    def __init__(
        self,
        instruction: str,
        model_name: str = Model.GEMINI_3_FLASH,
        max_steps: int = 100,
        api_key: str | None = None,
        enable_compression: bool = True,
        max_retries: int = 3,
        timeout: float = 30.0,
        max_history_turns: int = 3,
    ):
        self.instruction = instruction
        self.operation = Operation()
        self.lvm_chat = GeminiChat(
            api_key=api_key,
            model=model_name,
            enable_compression=enable_compression,
            max_retries=max_retries,
            timeout=timeout,
            max_history_turns=max_history_turns,
        )
        self.max_steps = max_steps
        self.s_dir = Path("screenshots")
        self.s_dir.mkdir(exist_ok=True)
        self.screen_width, self.screen_height = pyautogui.size()
        print(f"🖥️  屏幕尺寸: {self.screen_width} x {self.screen_height}")

        self.step_timings: list[dict] = []
        self._step_start_time: float = 0

    def normalize_coords(self, x: int, y: int) -> tuple[int, int]:
        actual_x = int(x / 1000.0 * self.screen_width)
        actual_y = int(y / 1000.0 * self.screen_height)
        print(f"    归一化坐标 ({x}, {y}) -> 实际坐标 ({actual_x}, {actual_y})")
        return actual_x, actual_y

    def take_screenshot(self, state: AgentState) -> AgentState:
        self._step_start_time = time.perf_counter()
        step = state.get("step", 0) + 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = str(self.s_dir / f"step_{step}_{timestamp}.png")
        screenshot_start = time.perf_counter()
        self.operation.screenshot(screenshot_path)
        screenshot_time = time.perf_counter() - screenshot_start
        print(f"    📸 截图耗时: {screenshot_time:.3f}s")
        return {
            **state,
            "screenshot_path": screenshot_path,
            "step": step,
            "finished": False,
        }

    def model_decide(self, state: AgentState) -> AgentState:
        prompt = COMPUTER_USE_UITARS.format(instruction=state["instruction"])
        response = self.lvm_chat.get_multimodal_response(
            text=prompt,
            image_paths=state["screenshot_path"],
            use_history=True,
        )
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
            "action": action,
        }

    def execute_action(self, state: AgentState) -> AgentState:
        action = state["action"]
        if not action:
            print("⚠️ 没有可执行的动作")
            return {**state, "finished": True}
        if action.startswith("finished("):
            content_match = re.search(r"finished\(content='([^']*)'\)", action)
            content = content_match.group(1) if content_match else "任务完成"
            print(f"✅ 任务完成: {content}")
            return {**state, "finished": True}
        try:
            self._parse_and_execute(action)
        except Exception as e:
            print(f"❌ 执行动作失败: {e}")
            print(f"   动作: {action}")

        step_time = time.perf_counter() - self._step_start_time
        self.step_timings.append(
            {
                "step": state["step"],
                "action": action[:50] + "..." if len(action) > 50 else action,
                "time": round(step_time, 2),
            }
        )
        print(f"    ⏱️ 步骤总耗时: {step_time:.2f}s")

        return state

    def _parse_and_execute(self, action: str):
        print(f"🔧 执行动作: {action}")
        if action.startswith("click("):
            point_match = re.search(r"<point>(\d+)\s+(\d+)</point>", action)
            if point_match:
                x, y = int(point_match.group(1)), int(point_match.group(2))
                actual_x, actual_y = self.normalize_coords(x, y)
                self.operation.click(actual_x, actual_y)
                self.operation.wait(0.5)
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
                self.operation.wait(0.5)
        elif action.startswith("left_double("):
            point_match = re.search(r"<point>(\d+)\s+(\d+)</point>", action)
            if point_match:
                x, y = int(point_match.group(1)), int(point_match.group(2))
                actual_x, actual_y = self.normalize_coords(x, y)
                self.operation.double_click(actual_x, actual_y)
                self.operation.wait(1)
        elif action.startswith("hotkey("):
            key_match = re.search(r"key=['\"]([^'\"]*)['\"]", action)
            if key_match:
                key_str = key_match.group(1)
                keys = key_str.split()
                self.operation.hotkey(*keys)
                self.operation.wait(0.5)
        elif action.startswith("wait()"):
            self.operation.wait(2)
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
                print(
                    f"📜 滚动: {direction} at ({actual_x}, {actual_y})，步长: {scroll_amount}"
                )
                self.operation.wait(0.5)
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
                self.operation.wait(0.5)
        else:
            print(f"⏸️  暂未实现的动作类型: {action.split('(')[0]}，程序将等待2秒。")
            self.operation.wait(2)

    def should_continue(self, state: AgentState) -> str:
        if state.get("finished", False):
            return "end"
        if state.get("step", 0) >= self.max_steps:
            print(f"⏹️ 已达到最大步骤数 {self.max_steps}，自动结束本次任务。")
            return "end"
        return "continue"

    def _print_final_stats(self):
        print("\n" + "=" * 60)
        print("📊 任务执行统计")
        print("=" * 60)

        if self.step_timings:
            print("\n📋 各步骤耗时:")
            total_step_time = 0
            for timing in self.step_timings:
                print(f"  Step {timing['step']}: {timing['time']}s - {timing['action']}")
                total_step_time += timing["time"]
            avg_step_time = total_step_time / len(self.step_timings)
            print(f"\n  总步骤数: {len(self.step_timings)}")
            print(f"  平均每步耗时: {avg_step_time:.2f}s")

        self.lvm_chat.print_performance_summary()

    def run(self):
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
            {"continue": "screenshot", "end": END},
        )
        app = workflow.compile()
        print(f"🚀 开始执行任务: {self.instruction}\n")
        config = {"recursion_limit": self.max_steps + 10}
        try:
            final_state = app.invoke(
                {"instruction": self.instruction, "step": 0},
                config=config,
            )
            print(f"\n🎉 任务结束! 共执行 {final_state.get('step', 0)} 步")
        except Exception as e:
            print(f"\n⚠️ 任务执行异常: {e}")
        finally:
            self._print_final_stats()


if __name__ == "__main__":
    your_instruction = "我想买一个手机，帮我看看哪个手机性价比高"
    agent = GUIAgent(instruction=your_instruction)
    agent.run()
