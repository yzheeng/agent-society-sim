"""LLM 客户端
"""
from __future__ import annotations

import inspect
import os

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage
from dotenv import load_dotenv

from society.config import load_config

load_dotenv()

_profile = load_config().llm.current()

if _profile.api_key_env:
    _api_key = os.environ.get(_profile.api_key_env)
    if not _api_key:
        raise RuntimeError(f"缺少 {_profile.api_key_env},请在项目根目录的 .env 里设置")
else:
    _api_key = "not-needed"  # LM Studio 等本地服务不校验 key,占位即可

_client = OpenAI(api_key=_api_key, base_url=_profile.base_url)

# SDK 的 create() 用显式签名,不认识的采样参数(如 top_k / min_p)直接传会抛 TypeError。
# 这里取出签名认识的参数名,调用时据此把私有参数路由进 extra_body 透传给后端。
_KNOWN_PARAMS = set(inspect.signature(_client.chat.completions.create).parameters)


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

    # profile.params 打底:SDK 签名认识的留在顶层,其余(top_k / min_p 等)进 extra_body 透传。
    extra_body = {k: v for k, v in _profile.params.items() if k not in _KNOWN_PARAMS}
    kwargs: dict = {k: v for k, v in _profile.params.items() if k in _KNOWN_PARAMS}
    # 核心字段(model / messages / stream)放右边后写,确保不被覆盖。
    kwargs.update(model=_profile.model, messages=messages, stream=False)
    if extra_body:
        kwargs["extra_body"] = extra_body
    if tools:
        kwargs["tools"] = tools
        # 注:不传 tool_choice ——DeepSeek thinking 模式下传 "required" 会 400。
        # 默认 "auto" + prompt 引导 + brain.py 兜底足够稳。

    resp = _client.chat.completions.create(**kwargs)
    return resp.choices[0].message


if __name__ == "__main__":
    reply = chat("用一句话介绍你自己。")
    print(reply.content)
