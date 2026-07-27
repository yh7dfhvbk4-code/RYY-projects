"""LLM 封装：OpenAI 兼容协议，DeepSeek / OpenAI 通过 base_url + model 切换。"""
import os

from openai import OpenAI

from rag import config
from rag.generation.prompts import SYSTEM_PROMPT


class LLMClient:
    """云端 LLM 客户端。

    api_key 优先级：显式传入 > 环境变量 LLM_API_KEY。
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("LLM_API_KEY")
        if not self._api_key:
            raise ValueError(
                "未提供 LLM API key：请传入 api_key 或设置环境变量 LLM_API_KEY"
            )
        self._base_url = base_url or config.LLM_BASE_URL
        self._model = model or config.LLM_MODEL
        self._client = OpenAI(
            api_key=self._api_key, base_url=self._base_url, max_retries=3
        )

    def generate(self, user_prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
        """单轮生成，返回模型文本输出。"""
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=config.LLM_TEMPERATURE,
                max_tokens=config.LLM_MAX_TOKENS,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise RuntimeError(
                f"LLM 生成失败（model={self._model}，base_url={self._base_url}）：{e}"
            ) from e
