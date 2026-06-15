"""
感知层:agent 这回合"能看见什么
"""
from __future__ import annotations
from dataclasses import dataclass, field

from society.core.models import Agent, Event, WorldState
from society.core.enums import Visibility


@dataclass
class Perception:
    self_agent: Agent              # 它自己(私密层在这里面:goal / secret / plan)
    visible_events: list[Event] = field(default_factory=list)  # 它能看见的公开事件
    others_present: list[Agent] = field(default_factory=list)  # 同地点还有谁在场


def perceive(world: WorldState, agent: Agent) -> Perception:
    """给定当前世界,输出 agent 自从上次自己动手之后,在身边发生的【新鲜】公开事件。

    时间边界是"自己上次的动作",不是 tick——这样每回合的第一发言者也能拾到上一
    回合后半段他人的发言作为 "此刻",而不会落到 "空气安静" 的 fallback。
    历史 (已被吸收进 memory 的事件) 交给 memory。
    """
    # 反向定位:event_log 中自己最后一条事件的下标(没有则 -1,即从头开始)
    cutoff = -1
    for i in range(len(world.event_log) - 1, -1, -1):
        if world.event_log[i].actor_id == agent.id:
            cutoff = i
            break

    visible_events = [
        e for e in world.event_log[cutoff + 1:]
        if e.location_id == agent.location_id
        and e.visibility == Visibility.PUBLIC
        and e.actor_id != agent.id
    ]

    others_present = [
        a for a in world.agents_at(agent.location_id)
        if a.id != agent.id
    ]

    return Perception(
        self_agent=agent,
        visible_events=visible_events,
        others_present=others_present,
    )