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
    """持有一张火种表 + 一个运行时注入队列,每拍开头决定注入哪些事件。

    两个来源:
    - 剧本预排的定时火种(_sparks):按 (day, phase, tick) 坐标命中即发。
    - 导演临场注入的火种(_queued):由 inject() 入队,下一次 sparks_for 立即发、发完即清。
    两者最终都走同一条 WORLD_ACTOR / PUBLIC 管线落进世界。
    """

    def __init__(self, sparks: list[Spark]) -> None:
        self._sparks = sparks
        self._queued: list[tuple[str, str]] = []  # (location_id, content),临场注入

    def inject(self, location_id: str, content: str) -> None:
        """导演之手:临场排一颗公开火种,下一拍立即注入。"""
        self._queued.append((location_id, content))

    def _spark_event(self, world: WorldState, location_id: str, content: str) -> Event:
        return Event(
            tick=world.tick,
            actor_id=WORLD_ACTOR,
            type=ActionType.ACT,
            content=content,
            location_id=location_id,
            visibility=Visibility.PUBLIC,
        )

    def sparks_for(self, world: WorldState) -> list[Event]:
        """返回本拍(world.tick 已自增到位)应注入世界的火种事件,可能为空。"""
        events: list[Event] = []
        if world.calendar is not None:
            day, phase, tick_in_phase = decompose(world.tick, world.calendar)
            events.extend(
                self._spark_event(world, s.location_id, s.content)
                for s in self._sparks
                if s.day == day and s.phase == phase and s.tick_in_phase == tick_in_phase
            )
        # 临场注入:无视时间坐标,本拍即发,发完清空。
        events.extend(self._spark_event(world, loc, content) for loc, content in self._queued)
        self._queued.clear()
        return events
