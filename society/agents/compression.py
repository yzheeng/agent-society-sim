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
    "下面那些片段是「我」最近一段时间真实经历过的事。\n"
    "\n"
    "请以「我」的口吻,把它们压成一段简短的回忆——把发生过的事一桩一桩留住骨架。"
    "谁说过什么大概意思、谁去了哪里、谁做了什么、我当时是什么感受,这些都该留下;"
    "但具体的措辞、动作细节、来回拌嘴可以淡化。\n"
    "\n"
    "就像几天后再回想:还能记得这段经历发生过什么、心里大概是什么感受,"
    "但很多原话已经记不清了。\n"
    "\n"
    "3-5 条,全文不超过 200 字。每条之间用一个空格分开,"
    "不要换行,不要用 - 项目符号,不要任何 markdown 格式。"
    "不要写「总结一下」「综上所述」「以上是」这类话。"
)


def maybe_compress(agent: Agent) -> None:
    cfg = load_config().memory.compression
    if len(agent.memory) < cfg.trigger_size:
        return

    split = len(agent.memory) - cfg.keep_recent
    head = agent.memory[:split]
    tail = agent.memory[split:]

    msg = chat("\n".join(head), system=_COMPRESSION_SYSTEM)
    # 单行化:LLM 不论塞 \n\n 段落还是 - bullet,都压平成一行。
    # memory 单条 = 单行是 prompts.py 渲染逻辑的隐式契约。
    summary = " ".join((msg.content or "").split())
    if not summary:
        # LLM 没给东西就别动 memory,等下一拍再试,反正不变式没破。
        return

    agent.memory[:] = [f"{_SUMMARY_PREFIX}{summary}"] + tail
