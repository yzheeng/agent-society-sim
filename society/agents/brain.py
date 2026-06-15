"""
决策层：agent根据input perception进行决策
"""
from __future__ import annotations

from society.core.models import Event
from society.core.enums import ActionType, Visibility
from society.engine.perception import Perception


def decide(perception: Perception, tick: int) -> Event:
    """吃一份感知,吐一个动作。当前用写死规则代替 LLM。"""
    me = perception.self_agent

    # —— 写死的假规则:屋里有别人就开口,没别人就想心事 ——
    if perception.others_present:
        # 当着人:说一句"对外"的话(PUBLIC)
        return Event(
            tick=tick,
            actor_id=me.id,
            type=ActionType.SPEAK,
            content=f"({me.name} 随口搭话)大家加油啊~",
            location_id=me.location_id,
            visibility=Visibility.PUBLIC,
        )
    else:
        # 没人时:暴露私密目标的心声(PRIVATE,永远只有它自己+上帝看得到)
        return Event(
            tick=tick,
            actor_id=me.id,
            type=ActionType.THINK,
            content=f"(心声){me.private_goal}……得想想办法。",
            location_id=me.location_id,
            visibility=Visibility.PRIVATE,
        )