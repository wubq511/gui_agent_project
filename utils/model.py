import base64
import hashlib
import json
import os
import time
from io import BytesIO
from typing import Any, Dict, List

from openai import OpenAI

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class Model:
    GEMINI_3_PRO = "gemini-3-pro"
    GEMINI_3_FLASH = "gemini-3-flash-preview"


class PerformanceMetrics:
    def __init__(self):
        self.api_calls = 0
        self.total_api_time = 0.0
        self.total_encode_time = 0.0
        self.total_compress_time = 0.0
        self.cache_hits = 0
        self.cache_misses = 0

    def record_api_call(self, duration: float):
        self.api_calls += 1
        self.total_api_time += duration

    def record_encode(self, duration: float):
        self.total_encode_time += duration

    def record_compress(self, duration: float):
        self.total_compress_time += duration

    def record_cache_hit(self):
        self.cache_hits += 1

    def record_cache_miss(self):
        self.cache_misses += 1

    def get_summary(self) -> Dict[str, Any]:
        avg_api_time = (
            self.total_api_time / self.api_calls if self.api_calls > 0 else 0
        )
        cache_hit_rate = (
            self.cache_hits / (self.cache_hits + self.cache_misses)
            if (self.cache_hits + self.cache_misses) > 0
            else 0
        )
        return {
            "api_calls": self.api_calls,
            "total_api_time": round(self.total_api_time, 2),
            "avg_api_time": round(avg_api_time, 2),
            "total_encode_time": round(self.total_encode_time, 2),
            "total_compress_time": round(self.total_compress_time, 2),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": f"{cache_hit_rate:.1%}",
        }


class ImageProcessor:
    IMAGE_QUALITY = int(os.getenv("GUI_AGENT_IMAGE_QUALITY", "70"))
    MAX_IMAGE_SIZE = int(os.getenv("GUI_AGENT_MAX_IMAGE_SIZE", "1280"))
    ENABLE_COMPRESSION = os.getenv("GUI_AGENT_ENABLE_COMPRESSION", "true").lower() == "true"

    _cache: Dict[str, str] = {}
    _cache_max_size = int(os.getenv("GUI_AGENT_CACHE_SIZE", "50"))

    @classmethod
    def _compute_hash(cls, image_path: str) -> str:
        hasher = hashlib.md5()
        with open(image_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def _resize_if_needed(cls, img) -> Any:
        if not PIL_AVAILABLE:
            return img
        width, height = img.size
        max_dim = max(width, height)
        if max_dim > cls.MAX_IMAGE_SIZE:
            scale = cls.MAX_IMAGE_SIZE / max_dim
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"    📐 图片缩放: {width}x{height} -> {new_width}x{new_height}")
        return img

    @classmethod
    def compress_and_encode(
        cls, image_path: str, metrics: PerformanceMetrics = None
    ) -> str:
        compress_start = time.perf_counter()

        enable_compression = cls.ENABLE_COMPRESSION and PIL_AVAILABLE

        if enable_compression:
            file_hash = cls._compute_hash(image_path)
            if file_hash in cls._cache:
                if metrics:
                    metrics.record_cache_hit()
                print(f"    🎯 图片缓存命中")
                return cls._cache[file_hash]

            if metrics:
                metrics.record_cache_miss()

        try:
            if enable_compression:
                img = Image.open(image_path)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                img = cls._resize_if_needed(img)

                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=cls.IMAGE_QUALITY, optimize=True)
                compressed_size = buffer.tell()
                original_size = os.path.getsize(image_path)
                compression_ratio = (1 - compressed_size / original_size) * 100
                print(
                    f"    🗜️ 图片压缩: {original_size / 1024:.1f}KB -> {compressed_size / 1024:.1f}KB ({compression_ratio:.1f}% 减少)"
                )

                encode_start = time.perf_counter()
                base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
                if metrics:
                    metrics.record_encode(time.perf_counter() - encode_start)

                if len(cls._cache) >= cls._cache_max_size:
                    oldest_key = next(iter(cls._cache))
                    del cls._cache[oldest_key]
                cls._cache[file_hash] = base64_str

            else:
                encode_start = time.perf_counter()
                with open(image_path, "rb") as f:
                    base64_str = base64.b64encode(f.read()).decode("utf-8")
                if metrics:
                    metrics.record_encode(time.perf_counter() - encode_start)

        except Exception as e:
            print(f"    ⚠️ 图片处理失败，使用原始方式: {e}")
            encode_start = time.perf_counter()
            with open(image_path, "rb") as f:
                base64_str = base64.b64encode(f.read()).decode("utf-8")
            if metrics:
                metrics.record_encode(time.perf_counter() - encode_start)

        if metrics:
            metrics.record_compress(time.perf_counter() - compress_start)

        return base64_str

    @classmethod
    def clear_cache(cls):
        cls._cache.clear()
        print("🗑️ 图片缓存已清空")


class GeminiChat:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = Model.GEMINI_3_FLASH,
        max_history_turns: int = 3,
        max_tokens: int = 512,
        enable_compression: bool = True,
        max_retries: int = 3,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.getenv("LINGYAAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "未提供 API Key，请在环境变量 LINGYAAI_API_KEY 中配置，"
                "或在初始化 GeminiChat 时传入 api_key 参数。"
            )
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout

        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.lingyaai.cn/v1",
            timeout=self.timeout,
            max_retries=max_retries,
        )

        self.conversation_history: List[Dict[str, Any]] = []
        self.max_history_turns = max(0, int(max_history_turns))
        self.max_tokens = max(64, int(max_tokens))
        self.metrics = PerformanceMetrics()
        self.enable_compression = enable_compression and PIL_AVAILABLE

        print(f"🔧 GeminiChat 初始化完成:")
        print(f"   - 模型: {model}")
        print(f"   - 历史轮数: {max_history_turns}")
        print(f"   - 最大tokens: {max_tokens}")
        print(f"   - 图片压缩: {'启用' if self.enable_compression else '禁用'}")
        print(f"   - 超时时间: {timeout}s")
        print(f"   - 最大重试: {max_retries}")

    def _build_history_messages(self) -> List[Dict[str, Any]]:
        if not self.conversation_history or self.max_history_turns <= 0:
            return []
        max_messages = self.max_history_turns * 2
        return self.conversation_history[-max_messages:]

    def _append_history(self, user_text: str, assistant_text: str) -> None:
        if self.max_history_turns <= 0:
            return
        self.conversation_history.append(
            {"role": "user", "content": user_text}
        )
        self.conversation_history.append(
            {"role": "assistant", "content": assistant_text}
        )
        max_messages = self.max_history_turns * 2
        if len(self.conversation_history) > max_messages:
            self.conversation_history = self.conversation_history[-max_messages:]

    def get_multimodal_response(
        self, text: str, image_paths: str, use_history: bool = True
    ) -> str:
        base64_image = ImageProcessor.compress_and_encode(
            image_paths, self.metrics if self.enable_compression else None
        )

        messages: List[Dict[str, Any]] = []
        if use_history and self.conversation_history:
            messages.extend(self._build_history_messages())

        current_message: Dict[str, Any] = {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
                {"type": "text", "text": text},
            ],
        }
        messages.append(current_message)

        api_start = time.perf_counter()
        try:
            print(f"🔄 正在调用API，模型: {self.model}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=0.1,
            )

            api_duration = time.perf_counter() - api_start
            self.metrics.record_api_call(api_duration)
            print(f"⏱️ API调用耗时: {api_duration:.2f}s")

            if hasattr(response, "choices"):
                result_text = response.choices[0].message.content
                print(f"✅ 成功获取响应，内容长度: {len(result_text)}")
            else:
                error_msg = "API响应格式异常"
                print(f"❌ {error_msg}")
                return json.dumps(
                    {"Thought": error_msg, "Action": "wait()"},
                    ensure_ascii=False,
                )

        except Exception as e:
            api_duration = time.perf_counter() - api_start
            self.metrics.record_api_call(api_duration)
            error_detail = f"API调用异常: {str(e)}"
            print(f"❌ {error_detail}")
            return json.dumps(
                {"Thought": error_detail, "Action": "wait()"},
                ensure_ascii=False,
            )

        if use_history:
            self._append_history(text, result_text)

        return result_text

    def clear_history(self):
        self.conversation_history = []
        ImageProcessor.clear_cache()
        print("🗑️ 历史记录和图片缓存已清空")

    def get_performance_summary(self) -> Dict[str, Any]:
        return self.metrics.get_summary()

    def print_performance_summary(self):
        summary = self.get_performance_summary()
        print("\n" + "=" * 50)
        print("📊 性能统计摘要")
        print("=" * 50)
        for key, value in summary.items():
            print(f"  {key}: {value}")
        print("=" * 50)
