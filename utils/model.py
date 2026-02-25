import base64
import json
import os
import time
import hashlib
from functools import lru_cache
from openai import OpenAI
from typing import List, Dict, Any, Optional
import threading


class Model:
    """模型枚举"""
    GEMINI_3_PRO = "gemini-3-pro"
    GEMINI_3_FLASH = "gemini-3-flash-preview"


class PerformanceStats:
    """性能统计工具类"""
    def __init__(self):
        self.stats: Dict[str, List[float]] = {}
        self._lock = threading.Lock()
    
    def record(self, operation: str, duration: float):
        with self._lock:
            if operation not in self.stats:
                self.stats[operation] = []
            self.stats[operation].append(duration)
    
    def get_summary(self) -> Dict[str, Dict[str, float]]:
        with self._lock:
            summary = {}
            for op, times in self.stats.items():
                if times:
                    summary[op] = {
                        "count": len(times),
                        "total": sum(times),
                        "avg": sum(times) / len(times),
                        "min": min(times),
                        "max": max(times),
                    }
            return summary


PERF_STATS = PerformanceStats()


class ImageCache:
    """图片编码缓存，避免重复编码相同图片"""
    def __init__(self, max_size: int = 100):
        self._cache: Dict[str, str] = {}
        self._max_size = max_size
        self._lock = threading.Lock()
    
    def get_or_encode(self, image_path: str) -> str:
        cache_key = self._get_cache_key(image_path)
        
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        with open(image_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("utf-8")
        
        with self._lock:
            if len(self._cache) >= self._max_size:
                self._cache.pop(next(iter(self._cache)))
            self._cache[cache_key] = encoded
        
        return encoded
    
    def _get_cache_key(self, image_path: str) -> str:
        try:
            mtime = os.path.getmtime(image_path)
            size = os.path.getsize(image_path)
            return f"{image_path}:{mtime}:{size}"
        except OSError:
            return image_path
    
    def clear(self):
        with self._lock:
            self._cache.clear()


IMAGE_CACHE = ImageCache()


class GeminiChat:
    """通过灵芽API调用Gemini的多模态聊天类（优化版）"""

    def __init__(
        self, 
        api_key: str = None, 
        model: str = Model.GEMINI_3_FLASH,
        max_history: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.api_key = api_key or os.getenv("LINGYAAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "未提供 API Key，请在环境变量 LINGYAAI_API_KEY 中配置，"
                "或在初始化 GeminiChat 时传入 api_key 参数。"
            )
        self.model = model
        self.max_history = max_history
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.lingyaai.cn/v1",
            timeout=60.0,
        )
        self.conversation_history: List[Dict[str, Any]] = []
        self._history_lock = threading.Lock()

    def _encode_image(self, image_path: str) -> str:
        return IMAGE_CACHE.get_or_encode(image_path)

    def _trim_history(self):
        """限制历史记录长度，防止无限增长"""
        with self._history_lock:
            if len(self.conversation_history) > self.max_history * 2:
                keep_count = self.max_history * 2
                self.conversation_history = self.conversation_history[-keep_count:]

    def _call_api_with_retry(
        self, 
        messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        """带重试机制的API调用"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=2048,
                    temperature=0.1,
                )
                
                duration = time.time() - start_time
                PERF_STATS.record("api_call", duration)
                
                if hasattr(response, "choices"):
                    return response.choices[0].message.content
                else:
                    last_error = "API响应格式异常"
                    
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    print(f"⚠️ API调用失败，{wait_time}秒后重试 ({attempt + 1}/{self.max_retries})")
                    time.sleep(wait_time)
        
        return None

    def get_multimodal_response(
        self, 
        text: str, 
        image_paths: str, 
        use_history: bool = True
    ) -> str:
        """支持记忆的图文对话（优化版）"""
        start_time = time.time()
        
        encode_start = time.time()
        base64_image = self._encode_image(image_paths)
        encode_duration = time.time() - encode_start
        PERF_STATS.record("image_encode", encode_duration)

        messages = []
        if use_history:
            with self._history_lock:
                messages.extend(self.conversation_history)

        current_message = {
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

        print(f"🔄 正在调用API，模型: {self.model}，历史消息数: {len(messages)-1}")

        result_text = self._call_api_with_retry(messages)
        
        if result_text is None:
            error_msg = f"API调用失败: {last_error if 'last_error' in dir() else '未知错误'}"
            print(f"❌ {error_msg}")
            return json.dumps(
                {"Thought": error_msg, "Action": "wait()"},
                ensure_ascii=False,
            )

        print(f"✅ 成功获取响应，内容长度: {len(result_text)}")

        if use_history:
            with self._history_lock:
                self.conversation_history.append(current_message)
                self.conversation_history.append({
                    "role": "assistant",
                    "content": result_text,
                })
            self._trim_history()

        total_duration = time.time() - start_time
        PERF_STATS.record("total_request", total_duration)
        
        return result_text

    def clear_history(self):
        """清空记忆"""
        with self._history_lock:
            self.conversation_history = []

    @staticmethod
    def get_performance_stats() -> Dict[str, Dict[str, float]]:
        """获取性能统计"""
        return PERF_STATS.get_summary()
