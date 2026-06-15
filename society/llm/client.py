"""LLM 客户端
"""
from __future__ import annotations

import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_api_key = os.environ.get("DEEPSEEK_API_KEY")
if not _api_key:
    raise RuntimeError("缺少 DEEPSEEK_API_KEY,请在项目根目录的 .env 里设置")

_BASE_URL = "https://api.deepseek.com"
_MODEL = "deepseek-v4-flash"

_client = OpenAI(api_key=_api_key, base_url=_BASE_URL)

def chat(prompt: str, system: str = "") -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = _client.chat.completions.create(
        model=_MODEL,
        messages=messages,
        stream=False,
    )
    return resp.choices[0].message.content


if __name__ == "__main__":
    reply = chat("用一句话介绍你自己。")
    print(reply)