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
    """给定当前的世界，输出agent当前回合的感知"""
    # 当前agent的可见事件
    visible_events = [
        e for e in world.event_log
        if e.location_id == agent.location_id
        and e.visibility == Visibility.PUBLIC
    ]

    # 同地点存在的其他人物
    others_present = [
        a for a in world.agents_at(agent.location_id)
        if a.id != agent.id
    ]

    return Perception(
        self_agent=agent,
        visible_events=visible_events,
        others_present=others_present,
    )