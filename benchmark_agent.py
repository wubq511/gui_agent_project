import time
from typing import Optional

from main import GUIAgent


def benchmark_run(instruction: str, repeat: int = 1, model_name: Optional[str] = None) -> None:
    """简单的端到端基准测试工具。

    注意：
    - 会真实调用多模态模型与操作系统 GUI，请在可控环境下使用；
    - 建议在同一台机器上对比「优化前 / 优化后」的平均耗时；
    - 如需更快测试，可将指令改为简单任务并降低 max_steps。
    """
    total = 0.0
    for i in range(repeat):
        print(f"\n====== Benchmark 第 {i + 1}/{repeat} 轮 ======")
        agent = GUIAgent(
            instruction=instruction,
            model_name=model_name if model_name is not None else None,
        )
        start = time.perf_counter()
        agent.run()
        elapsed = time.perf_counter() - start
        print(f"⏱️ 本轮耗时: {elapsed:.2f} 秒")
        total += elapsed

    avg = total / repeat if repeat > 0 else 0.0
    print(f"\n🏁 基准测试完成，平均耗时: {avg:.2f} 秒（共 {repeat} 轮）")


if __name__ == "__main__":
    # 示例用法：可根据需要修改指令与轮数
    benchmark_instruction = "打开浏览器并搜索一条简单信息，然后结束任务。"
    benchmark_run(benchmark_instruction, repeat=1)

