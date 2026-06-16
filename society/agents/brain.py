"""
agent行动层
"""
from __future__ import annotations

from society.core.models import Event
from society.core.enums import ActionType
from society.engine.perception import Perception
from society.llm.client import chat
from society.agents.prompts import SYSTEM_PROMPT, build_user_prompt, parse_response
from society.agents.memory import recall


def decide(perception: Perception, tick: int) -> list[Event]:
    me = perception.self_agent
    # 取短期记忆,和感知一起拼进 prompt
    recalled = recall(me)
    user_prompt = build_user_prompt(perception, recalled)
    # llm
    raw = chat(user_prompt, system=SYSTEM_PROMPT)
    parsed = parse_response(raw)

    events: list[Event] = []
    for action in parsed:
        if action.action_type == ActionType.MOVE:
            # destination 必须在世界目录里;不合法就静默丢弃这次移动(fail-safe)
            if action.destination_id not in perception.location_catalog:
                continue
            if action.destination_id == me.location_id:
                # 已经在目的地了,不必动
                continue
            events.append(
                Event(
                    tick=tick,
                    actor_id=me.id,
                    type=ActionType.MOVE,
                    content="",  # 内容由 apply_event 用模板渲染
                    location_id=me.location_id,  # 出发地
                    destination_id=action.destination_id,
                    visibility=action.visibility,
                )
            )
        else:
            events.append(
                Event(
                    tick=tick,
                    actor_id=me.id,
                    type=action.action_type,
                    content=action.content,
                    location_id=me.location_id,
                    visibility=action.visibility,
                )
            )
    return events