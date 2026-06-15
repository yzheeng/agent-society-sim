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
    """给定当前世界，输出 agent 这一拍能合法感知到的【新鲜】信息。
    只看本回合(world.tick)在当前地点发生的 PUBLIC 事件——历史交给 memory,
    """
    visible_events = [
        e for e in world.event_log
        if e.location_id == agent.location_id
        and e.visibility == Visibility.PUBLIC
        and e.tick == world.tick
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