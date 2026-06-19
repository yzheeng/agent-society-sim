"""短期记忆压缩:把超出阈值的旧记忆滚动压成单条第一人称梗概。

不变式
- agent.memory 里的所有条目,要么以原文形式进 prompt,要么以摘要形式进 prompt;
  绝不允许"既不进 prompt、也没被压缩"的中间区。所以 recall 不再做截断,
  压缩在这里兜底 memory 的物理长度。
- 摘要存在 agent.memory[0],以 _SUMMARY_PREFIX 开头;其余条目是未压缩原文。
  再次触发时,旧摘要会和它后面那段早期原文一起被卷进新摘要——梗概递归滚动。

调用约定
- turn_engine 每个 agent remember() 之后调一次 maybe_compress(agent)。
- 内部按 config 判定要不要真的触发 LLM,空跑也安全。
"""
from __future__ import annotations

from society.config import load_config
from society.core.models import Agent
from society.llm.client import chat


_SUMMARY_PREFIX = "【此前梗概】"

_COMPRESSION_SYSTEM = (
    "下面那些片段是「我」最近一段时间真实经历过的事——说过的话、听到的话、"
    "心里掠过的念头、做过的动作。请以「我」的口吻,把它们压成一段连贯的回忆,"
    "保留关键人物、关键事件、关键情绪、还没解开的张力。\n"
    "不要列点,不要分段,不要写「总结一下」「综上所述」「以上是」这类话——"
    "就像我自己事后回想起这一段日子,自然地讲出来。"
)


def maybe_compress(agent: Agent) -> None:
    cfg = load_config().memory.compression
    if len(agent.memory) < cfg.trigger_size:
        return

    split = len(agent.memory) - cfg.keep_recent
    head = agent.memory[:split]
    tail = agent.memory[split:]

    msg = chat("\n".join(head), system=_COMPRESSION_SYSTEM)
    summary = (msg.content or "").strip()
    if not summary:
        # LLM 没给东西就别动 memory,等下一拍再试,反正不变式没破。
        return

    agent.memory[:] = [f"{_SUMMARY_PREFIX}{summary}"] + tail
