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
    """把这一拍 agent 的第一人称经历追加进短期记忆。

    两个来源,按时序拼接:
    1. perception_events: 我刚刚感知到的别人公开发言(自上次 remember 以来累积的)
    2. my_events: 我这一拍自己说的 / 想的 / 盘算的

    perception 不会与已有 memory 重叠——perceive() 只返回"我上次动作之后"的事件,
    而这些事件在此处会被吸收进 memory,所以不会再出现在下一次 perceive() 的结果里。
    """
    for e in perception_events:
        speaker = world.agents[e.actor_id].name if e.actor_id in world.agents else e.actor_id
        if e.type == ActionType.SPEAK:
            agent.memory.append(f"我听到 {speaker} 说:「{e.content}」")
        elif e.type == ActionType.ACT:
            agent.memory.append(f"我看到 {speaker}:{e.content}")
        elif e.type == ActionType.MOVE:
            # content 已是模板渲染好的"X 离开了,去往 Y" 或 "X 来了"
            agent.memory.append(f"我看到 {e.content}")

    for e in my_events:
        if e.type == ActionType.SPEAK:
            agent.memory.append(f"我说过:「{e.content}」")
        elif e.type == ActionType.THINK:
            agent.memory.append(f"我心里掠过:「{e.content}」")
        elif e.type == ActionType.PLAN:
            agent.memory.append(f"我盘算着:「{e.content}」")
        elif e.type == ActionType.ACT:
            agent.memory.append(f"我做了:{e.content}")
        elif e.type == ActionType.MOVE:
            # 自己永远 perceive 不到自己的两条 MOVE,得在这里给自己留一条"换地"的痕迹
            dest = world.locations.get(e.destination_id) if e.destination_id else None
            dest_name = dest.name if dest else e.destination_id
            agent.memory.append(f"我去了 {dest_name}")


def recall(agent: Agent, max_items: int = 100) -> list[str]:
    """取出喂给 prompt 的短期记忆。

    现在:直接截断,保留最近 max_items 条。
    以后升级长期记忆时,**只改这个函数**——把超出窗口的旧记忆压缩成摘要
    拼在返回结果前面,prompt 构建那边一行都不用动。这是预留的升级口子。
    """
    return agent.memory[-max_items:]
