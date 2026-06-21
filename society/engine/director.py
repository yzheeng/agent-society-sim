"""导演层:在 agent 自由意志之外,往世界里注入外部火种。

只跑 agent 循环的世界容易陷入"僵持均衡"——每个人的局部最优都是再忍一拍,
盖子永远不揭。director 负责制造非走不可的局面:把外部事件(手机震动、撞见、
广播通知……)作为旁白注入 event_log。落点和可见性复用既有感知管线——
事件挂在某个 location 上、标 PUBLIC,在场的 agent 下一拍 perceive 自然能拾到。

火种是【数据】,写在 scenario 里;这个文件只提供触发机制。
"""
from __future__ import annotations

from dataclasses import dataclass

from society.core.clock import decompose
from society.core.enums import ActionType, Visibility
from society.core.models import Event, WorldState, WORLD_ACTOR


@dataclass(frozen=True)
class Spark:
    """一颗外部火种:某天某时段的某一拍,在某地点发生的旁白事件。

    时间用 (day, phase, tick_in_phase) 标定——和 prompt 渲染的时段感同一套坐标,
    编剧按"第几天、哪个时段、第几拍"排布即可,不必换算成裸 tick。
    """
    day: int
    phase: str
    tick_in_phase: int
    location_id: str
    content: str


class Director:
    """持有一张火种表,每拍开头按当前时间坐标决定注入哪些事件。"""

    def __init__(self, sparks: list[Spark]) -> None:
        self._sparks = sparks

    def sparks_for(self, world: WorldState) -> list[Event]:
        """返回本拍(world.tick 已自增到位)应注入世界的火种事件,可能为空。"""
        if world.calendar is None:
            return []
        day, phase, tick_in_phase = decompose(world.tick, world.calendar)
        return [
            Event(
                tick=world.tick,
                actor_id=WORLD_ACTOR,
                type=ActionType.ACT,
                content=s.content,
                location_id=s.location_id,
                visibility=Visibility.PUBLIC,
            )
            for s in self._sparks
            if s.day == day and s.phase == phase and s.tick_in_phase == tick_in_phase
        ]
