"""agent 的运行时记忆(MVP:短期记忆 = 第一人称经历流)。

只做两件事:
- remember(): 回合末把"我这一拍的经历"追加进 agent.memory
- recall():   取最近 N 条喂给 prompt(现在是截断;以后在这里接长期记忆压缩)

不做持久化、不做长期记忆压缩——那些是后续。
"""
from __future__ import annotations

from society.core.models import Agent, Event, WorldState
from society.core.enums import ActionType


def remember(
    agent: Agent,
    world: WorldState,
    perception_events: list[Event],
    my_events: list[Event],
) -> None:
    """把这一拍 agent 的第一人称经历追加进它的短期记忆。

    两个来源:
    1. 我感知到的别人的公开发言(来自 perception,即 perception_events)
    2. 我自己这一拍的产出(说的话 + 心声 + 盘算,即 my_events)——
       心声 / 盘算不经过 perception,必须在这里显式记下,否则下一拍就丢了。

    写出来的字符串会被原样塞回 prompt 喂给 LLM,所以叙述视角必须始终是角色第一人称,
    不带任何"第 N 回合"之类的调度结构痕迹——顺序由 list 的追加顺序天然承载。
    """
    # 1) 我听到别人说的
    for e in perception_events:
        speaker = world.agents[e.actor_id].name if e.actor_id in world.agents else e.actor_id
        agent.memory.append(f"我听到 {speaker} 说:「{e.content}」")

    # 2) 我自己说的 / 想的 / 盘算的
    for e in my_events:
        if e.type == ActionType.SPEAK:
            agent.memory.append(f"我说过:「{e.content}」")
        elif e.type == ActionType.THINK:
            agent.memory.append(f"我心里掠过:「{e.content}」")
        elif e.type == ActionType.PLAN:
            agent.memory.append(f"我盘算着:「{e.content}」")
        # MOVE / ACT 暂不处理


def recall(agent: Agent, max_items: int = 100) -> list[str]:
    """取出喂给 prompt 的短期记忆。

    现在:直接截断,保留最近 max_items 条。
    以后升级长期记忆时,**只改这个函数**——把超出窗口的旧记忆压缩成摘要
    拼在返回结果前面,prompt 构建那边一行都不用动。这是预留的升级口子。
    """
    return agent.memory[-max_items:]
