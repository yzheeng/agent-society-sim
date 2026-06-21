"""agent 的运行时记忆:短期记忆 = 第一人称经历流。

只做两件事:
- remember(): 回合末把"我这一拍的经历"追加进 agent.memory
- recall():   把 memory 整体交给 prompt 拼装

memory 的物理长度由 society.agents.compression.maybe_compress() 在回合末兜底——
超出阈值时旧记忆会被滚动压成单条「梗概」塞回 memory[0],所以这里不再做截断。
"""
from __future__ import annotations

from society.core.models import Agent, Event, WorldState, WORLD_ACTOR
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
        if e.actor_id == WORLD_ACTOR:
            # 外部火种:以"我注意到"的旁观口吻沉进记忆,内容本身就是旁白。
            agent.memory.append(f"我注意到:{e.content}")
            continue
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


def recall(agent: Agent) -> list[str]:
    """把 agent 的整段 memory 交给 prompt 构建侧使用。

    memory 物理长度已由 compression.maybe_compress() 在回合末控制——头部可能是
    一条「梗概」滚动摘要,其余是未压缩的最近原文。这里不做截断、不做裁剪。
    """
    return list(agent.memory)
