import time
import argparse
from typing import Optional

from main import GUIAgent


def benchmark_run(
    instruction: str,
    repeat: int = 1,
    model_name: Optional[str] = None,
    enable_compression: bool = True,
    max_retries: int = 3,
    timeout: float = 30.0,
    max_history_turns: int = 3,
) -> dict:
    """端到端基准测试工具，支持性能优化参数配置。

    返回:
        dict: 包含测试结果的字典
    """
    results = []
    total = 0.0

    for i in range(repeat):
        print(f"\n{'='*60}")
        print(f"====== Benchmark 第 {i + 1}/{repeat} 轮 ======")
        print(f"{'='*60}")

        agent_kwargs = {"instruction": instruction}
        if model_name is not None:
            agent_kwargs["model_name"] = model_name
        agent_kwargs["enable_compression"] = enable_compression
        agent_kwargs["max_retries"] = max_retries
        agent_kwargs["timeout"] = timeout
        agent_kwargs["max_history_turns"] = max_history_turns

        agent = GUIAgent(**agent_kwargs)
        start = time.perf_counter()
        agent.run()
        elapsed = time.perf_counter() - start

        print(f"\n⏱️ 本轮耗时: {elapsed:.2f} 秒")
        total += elapsed
        results.append(
            {
                "round": i + 1,
                "time": elapsed,
                "performance": agent.lvm_chat.get_performance_summary(),
            }
        )

    avg = total / repeat if repeat > 0 else 0.0
    print(f"\n{'='*60}")
    print(f"🏁 基准测试完成")
    print(f"{'='*60}")
    print(f"  总轮数: {repeat}")
    print(f"  总耗时: {total:.2f} 秒")
    print(f"  平均耗时: {avg:.2f} 秒")

    return {
        "total_time": total,
        "average_time": avg,
        "rounds": repeat,
        "results": results,
    }


def compare_optimizations(instruction: str, repeat: int = 1):
    """对比优化前后的性能差异"""
    print("\n" + "=" * 70)
    print("🔬 性能优化对比测试")
    print("=" * 70)

    print("\n📊 测试配置:")
    print(f"  - 指令: {instruction[:50]}...")
    print(f"  - 重复次数: {repeat}")

    print("\n" + "-" * 70)
    print("📌 测试1: 禁用所有优化（基准线）")
    print("-" * 70)
    baseline_result = benchmark_run(
        instruction=instruction,
        repeat=repeat,
        enable_compression=False,
        max_history_turns=0,
    )

    print("\n" + "-" * 70)
    print("📌 测试2: 启用图片压缩")
    print("-" * 70)
    compression_result = benchmark_run(
        instruction=instruction,
        repeat=repeat,
        enable_compression=True,
        max_history_turns=0,
    )

    print("\n" + "-" * 70)
    print("📌 测试3: 启用所有优化（压缩 + 历史管理）")
    print("-" * 70)
    optimized_result = benchmark_run(
        instruction=instruction,
        repeat=repeat,
        enable_compression=True,
        max_history_turns=3,
    )

    print("\n" + "=" * 70)
    print("📊 对比结果汇总")
    print("=" * 70)

    baseline_avg = baseline_result["average_time"]
    compression_avg = compression_result["average_time"]
    optimized_avg = optimized_result["average_time"]

    compression_improvement = (
        (baseline_avg - compression_avg) / baseline_avg * 100 if baseline_avg > 0 else 0
    )
    optimized_improvement = (
        (baseline_avg - optimized_avg) / baseline_avg * 100 if baseline_avg > 0 else 0
    )

    print(f"\n  {'测试配置':<30} {'平均耗时':<15} {'提升比例':<15}")
    print(f"  {'-'*60}")
    print(f"  {'基准线（无优化）':<30} {baseline_avg:.2f}s{'':<8} {'-':<15}")
    print(
        f"  {'启用图片压缩':<30} {compression_avg:.2f}s{'':<8} {compression_improvement:+.1f}%"
    )
    print(
        f"  {'全部优化':<30} {optimized_avg:.2f}s{'':<8} {optimized_improvement:+.1f}%"
    )

    print("\n💡 优化建议:")
    if compression_improvement > 10:
        print("  ✅ 图片压缩效果显著，建议启用")
    if optimized_improvement > compression_improvement + 5:
        print("  ✅ 历史管理带来额外提升，建议启用")
    if optimized_improvement < 5:
        print("  ⚠️ 优化效果有限，可能网络延迟是主要瓶颈")

    return {
        "baseline": baseline_result,
        "compression_only": compression_result,
        "fully_optimized": optimized_result,
        "improvements": {
            "compression": compression_improvement,
            "fully_optimized": optimized_improvement,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GUI Agent 性能基准测试工具")
    parser.add_argument(
        "--instruction",
        "-i",
        type=str,
        default="打开浏览器并查询天气，然后结束任务。",
        help="测试指令",
    )
    parser.add_argument(
        "--repeat", "-r", type=int, default=1, help="重复测试次数"
    )
    parser.add_argument(
        "--compare", "-c", action="store_true", help="运行优化对比测试"
    )
    parser.add_argument(
        "--model", "-m", type=str, default=None, help="指定模型名称"
    )
    parser.add_argument(
        "--no-compression", action="store_true", help="禁用图片压缩"
    )
    parser.add_argument(
        "--timeout", "-t", type=float, default=30.0, help="API超时时间（秒）"
    )
    parser.add_argument(
        "--history-turns",
        type=int,
        default=3,
        help="历史对话轮数上限",
    )

    args = parser.parse_args()

    if args.compare:
        compare_optimizations(instruction=args.instruction, repeat=args.repeat)
    else:
        benchmark_run(
            instruction=args.instruction,
            repeat=args.repeat,
            model_name=args.model,
            enable_compression=not args.no_compression,
            timeout=args.timeout,
            max_history_turns=args.history_turns,
        )
