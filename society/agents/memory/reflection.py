"""语义记忆的生成引擎:周期性把情景经历蒸馏成持久信念(belief)。

reflection 与 compression 是姊妹过程,都在回合末读 agent 的工作记忆,但方向不同:
- compression 把旧经历【压成回忆】(还是经历,只是省地方);
- reflection  把经历【炼成结论】(我现在认定了什么),写回 agent.beliefs。

设计约束
- 只产「认知」(我怎么看人看事),不产「策略」(我下一步做什么)——这是社会模拟,
  反思若开始替 agent 规划行动,就把 emergent 推成了 strategic,刻意不要。
- beliefs 有界:每次反思把「旧信念 + 新经历」一起交给 LLM 重新沉淀,封顶
  cfg.max_beliefs,旧认知可被新认知挤出,绝不无限增长(同 compression 给 memory 兜底)。
- 沉浸不穿帮:系统提示以「我」的第一人称回望,不让模型察觉到这是模拟。

调用约定
- turn_engine 每个 agent remember() 之后、maybe_compress() 之前调一次 maybe_reflect。
  放在压缩之前,是为了让反思读到「被压缩溶解之前」最丰富的那版记忆。
- 内部按 config 判定要不要真的触发 LLM(只在 tick 落在 interval 上),空跑安全。
"""
from __future__ import annotations

import re

from society.config import load_config
from society.core.models import Agent, WorldState
from society.llm.client import chat


_REFLECTION_SYSTEM = (
    "下面是「我」心里已有的一些笃定看法,还有我最近一段时间真实经历过的事。\n"
    "\n"
    "请以「我」的口吻,回头想想这段日子——哪些事让我对别人、对自己、对眼下的处境,"
    "生出了或印证了某种挥之不去的认定。把它们沉淀成几条简短的看法。\n"
    "\n"
    "只写我【认定了什么】(对人对事的判断、对自己处境的体会),"
    "不要写我【打算做什么】(下一步的计划、行动)。\n"
    "已有的看法若被最近的事推翻或改写,就更新它、甚至丢掉它;没被触动的就照旧留着。\n"
    "\n"
    "最多 {max_beliefs} 条,从最笃定的写起。每条一行、一句话,"
    "不要分点编号,不要 - 项目符号,不要任何 markdown,不要写「总结」「综上」这类话。"
)

# 去掉 LLM 可能擅自加的行首项目符号 / 编号("- " "* " "1. " "1、" 等)。
_BULLET = re.compile(r"^(?:[-*•·]+\s*|\d+[.、)]\s*)")


def _parse_beliefs(raw: str, cap: int) -> list[str]:
    """把 LLM 的多行输出解析成 belief 列表:逐行去符号、单行化、封顶 cap。

    beliefs 是 list[str] 且每条单行(prompts.py:78 `- {b}` 渲染契约),
    所以这里一行 = 一条信念,绝不保留行内换行。
    """
    out: list[str] = []
    for line in raw.splitlines():
        s = _BULLET.sub("", line.strip())
        s = " ".join(s.split())
        if not s:
            continue
        out.append(s)
        if len(out) >= cap:
            break
    return out


def maybe_reflect(agent: Agent, world: WorldState) -> None:
    cfg = load_config().memory.reflection
    if cfg.interval <= 0 or world.tick % cfg.interval != 0:
        return
    if not agent.memory:
        # 还没积累任何经历,无可蒸馏。
        return

    # 把「我是谁/我要什么」当透镜垫在最前,再给旧信念 + 新经历。
    parts: list[str] = [f"我心底真正想要的,是{agent.private_goal}。", ""]
    if agent.beliefs:
        parts.append("我心里已经认定的事:")
        parts.extend(agent.beliefs)
        parts.append("")
    parts.append("我最近经历的事:")
    parts.extend(agent.memory)

    system = _REFLECTION_SYSTEM.format(max_beliefs=cfg.max_beliefs)
    msg = chat("\n".join(parts), system=system)
    beliefs = _parse_beliefs(msg.content or "", cfg.max_beliefs)
    if not beliefs:
        # LLM 没给出可用内容就别动 beliefs,保持原样,下次反思再说。
        return

    # 整体替换:LLM 已被要求「合并旧看法 + 新经历」,产出即是新的完整信念集。
    agent.beliefs[:] = beliefs
