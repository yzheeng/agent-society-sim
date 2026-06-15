"""
agent行动层
"""
from __future__ import annotations

from society.core.models import Event
from society.engine.perception import Perception
from society.llm.client import chat
from society.agents.prompts import SYSTEM_PROMPT, build_user_prompt, parse_response


def decide(perception: Perception, tick: int) -> Event:
    me = perception.self_agent
    # 把agent的感知构建成prompt
    user_prompt = build_user_prompt(perception)
    # llm
    raw = chat(user_prompt, system=SYSTEM_PROMPT)
    ## llm response
    action_type, visibility, content = parse_response(raw)
    return Event(
        tick=tick,
        actor_id=me.id,
        type=action_type,
        content=content,
        location_id=me.location_id,
        visibility=visibility,
    )