"""LLM 客户端
"""
from __future__ import annotations

import os

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage
from dotenv import load_dotenv

from society.config import load_config

load_dotenv()

_cfg = load_config().llm
_api_key = os.environ.get(_cfg.api_key_env)
if not _api_key:
    raise RuntimeError(f"缺少 {_cfg.api_key_env},请在项目根目录的 .env 里设置")

_client = OpenAI(api_key=_api_key, base_url=_cfg.base_url)


def chat(
    prompt: str,
    system: str = "",
    tools: list[dict] | None = None,
) -> ChatCompletionMessage:
    """调一次 LLM,返回 message 整体。

    传了 tools 就走 tool calling(强制 tool_choice=required);否则走自由文本。
    调用方决定取 .content(自由文本)还是 .tool_calls(tool 调用列表)。
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs: dict = {"model": _cfg.model, "messages": messages, "stream": False}
    if tools:
        kwargs["tools"] = tools
        # 注:不传 tool_choice ——DeepSeek thinking 模式下传 "required" 会 400。
        # 默认 "auto" + prompt 引导 + brain.py 兜底足够稳。

    resp = _client.chat.completions.create(**kwargs)
    return resp.choices[0].message


if __name__ == "__main__":
    reply = chat("用一句话介绍你自己。")
    print(reply.content)
