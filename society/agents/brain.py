"""
agent行动层
"""
from __future__ import annotations

from society.core.models import Event
from society.engine.perception import Perception
from society.llm.client import chat
from society.agents.prompts import SYSTEM_PROMPT, build_user_prompt, parse_response


def decide(perception: Perception, tick: int) -> list[Event]:
    me = perception.self_agent
    # 把 agent 的感知构建成 prompt
    user_prompt = build_user_prompt(perception)
    # llm
    raw = chat(user_prompt, system=SYSTEM_PROMPT)
    # 解析:现在拿到的是一串 (action_type, visibility, content)
    parsed = parse_response(raw)

    events: list[Event] = []
    for action_type, visibility, content in parsed:
        events.append(
            Event(
                tick=tick,
                actor_id=me.id,
                type=action_type,
                content=content,
                location_id=me.location_id,
                visibility=visibility,
            )
        )
    return events