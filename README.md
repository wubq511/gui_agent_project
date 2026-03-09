# GUI Agent Project

基于大语言模型的 GUI 自动化代理，能够理解屏幕内容并自动执行鼠标键盘操作。

## 功能特性

- **智能屏幕理解**：使用视觉语言模型（Gemini）分析屏幕截图，理解当前界面状态
- **自动化操作**：支持点击、双击、输入文本、快捷键、滚动、拖拽等常见 GUI 操作
- **工作流引擎**：基于 LangGraph 构建的状态机工作流，支持循环决策
- **性能优化**：图片压缩、缓存机制、历史对话管理
- **基准测试**：内置性能测试工具，支持优化对比分析

## 项目结构

```
gui_agent_project/
├── main.py              # 主程序入口，GUIAgent 核心类
├── benchmark_agent.py   # 性能基准测试工具
├── requirements.txt     # 项目依赖
├── gui_operator/
│   └── execute.py       # GUI 操作封装（点击、输入、截图等）
├── utils/
│   ├── __init__.py
│   ├── model.py         # 模型调用、图片处理、性能统计
│   └── prompts.py       # 提示词模板
└── tests/
    └── test_hotkey.py   # 测试文件
```

## 支持的操作

| 操作 | 格式 | 说明 |
|------|------|------|
| 单击 | `click(point='<point>x y</point>')` | 点击指定坐标 |
| 双击 | `left_double(point='<point>x y</point>')` | 双击指定坐标 |
| 输入 | `type(content='文本内容')` | 输入文本（支持中文） |
| 快捷键 | `hotkey(key='ctrl c')` | 按下组合键 |
| 滚动 | `scroll(point='<point>x y</point>', direction='down')` | 滚动页面 |
| 拖拽 | `drag(start_point='<point>x1 y1</point>', end_point='<point>x2 y2</point>')` | 拖拽操作 |
| 等待 | `wait()` | 等待 5 秒 |
| 完成 | `finished(content='任务总结')` | 标记任务完成 |

## 环境要求

- Python 3.10+
- Windows / macOS / Linux

## 安装

```bash
# 克隆项目
git clone https://github.com/your-username/gui_agent_project.git
cd gui_agent_project

# 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS

# 安装依赖
pip install -r requirements.txt
```

## 配置

在运行前，需要配置 API Key：

```bash
# Windows
set LINGYAAI_API_KEY=your_api_key_here

# Linux/macOS
export LINGYAAI_API_KEY=your_api_key_here
```

或者在代码中直接传入：

```python
agent = GUIAgent(
    instruction="你的任务指令",
    api_key="your_api_key_here"
)
```

## 快速开始

```python
from main import GUIAgent

# 创建代理实例
agent = GUIAgent(
    instruction="打开浏览器，搜索 Python 教程",
    max_steps=50  # 最大执行步数
)

# 运行代理
agent.run()
```

## 环境变量配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `LINGYAAI_API_KEY` | - | API 密钥（必需） |
| `GUI_AGENT_SPEED` | 1.0 | 操作速度倍率（越大越慢） |
| `GUI_AGENT_IMAGE_QUALITY` | 70 | 图片压缩质量 |
| `GUI_AGENT_MAX_IMAGE_SIZE` | 1280 | 图片最大尺寸 |
| `GUI_AGENT_ENABLE_COMPRESSION` | true | 是否启用图片压缩 |
| `GUI_AGENT_CACHE_SIZE` | 50 | 图片缓存大小 |

## 基准测试

项目内置性能测试工具：

```bash
# 基本测试
python benchmark_agent.py -i "打开记事本并输入 Hello World" -r 3

# 优化对比测试
python benchmark_agent.py -i "你的测试指令" --compare

# 指定模型和参数
python benchmark_agent.py -i "测试指令" -m gemini-3-flash-preview -t 60
```

### 命令行参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `--instruction` | `-i` | 测试指令 |
| `--repeat` | `-r` | 重复次数 |
| `--compare` | `-c` | 运行优化对比测试 |
| `--model` | `-m` | 指定模型名称 |
| `--no-compression` | - | 禁用图片压缩 |
| `--timeout` | `-t` | API 超时时间（秒） |
| `--history-turns` | - | 历史对话轮数上限 |

## 工作原理

1. **截图**：捕获当前屏幕状态
2. **决策**：将截图发送给视觉语言模型，获取下一步操作
3. **执行**：解析模型输出，执行对应的 GUI 操作
4. **循环**：重复以上步骤直到任务完成或达到最大步数

```
┌─────────┐    ┌─────────┐    ┌─────────┐
│ 截图    │───▶│ 模型决策 │───▶│ 执行操作 │
└─────────┘    └─────────┘    └─────────┘
     ▲                              │
     └──────────────────────────────┘
```

## 注意事项

- 运行时请勿移动鼠标，以免干扰自动化操作
- 建议在测试环境中先验证指令效果
- 部分操作可能需要管理员权限
- 首次运行会创建 `screenshots/` 目录保存截图

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。
