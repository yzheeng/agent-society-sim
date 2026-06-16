"""LLM 客户端
"""
from __future__ import annotations

import os

from openai import OpenAI
from dotenv import load_dotenv

from society.config import load_config

load_dotenv()

_cfg = load_config().llm
_api_key = os.environ.get(_cfg.api_key_env)
if not _api_key:
    raise RuntimeError(f"缺少 {_cfg.api_key_env},请在项目根目录的 .env 里设置")

_client = OpenAI(api_key=_api_key, base_url=_cfg.base_url)


def chat(prompt: str, system: str = "") -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = _client.chat.completions.create(
        model=_cfg.model,
        messages=messages,
        stream=False,
    )
    return resp.choices[0].message.content


if __name__ == "__main__":
    reply = chat("用一句话介绍你自己。")
    print(reply)
