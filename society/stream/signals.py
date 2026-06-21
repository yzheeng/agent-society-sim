"""引擎 → 外界 的数据契约。

引擎不再直接 print,而是把"刚发生了什么"打包成 Signal 交给一个 SimSink。
sink 的具体实现(CLI / TUI / WebSocket / 回放写文件……)都住在 ui 层,
引擎只认这里的 Protocol。

每个 Signal 都自带 TimeStamp:绝对 tick 必填,calendar 推得出的
day/phase/tick_in_phase 收进可选的嵌套 SceneStamp——这样消费方一次
`if time.scene` 即可分支,不会随字段增多腐烂。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from society.core.clock import decompose
from society.core.models import Event, WorldState


@dataclass(frozen=True)
class SceneStamp:
    day: int
    phase: str
    tick_in_phase: int


@dataclass(frozen=True)
class TimeStamp:
    tick: int
    scene: SceneStamp | None = None


@dataclass(frozen=True)
class TickStarted:
    time: TimeStamp


@dataclass(frozen=True)
class WorldEventEmitted:
    """一条已落子的 in-world 事件。raw event 直接挂着,actor / location 名字
    在引擎一侧解析好,免得 sink 还要 hold world ref。"""
    time: TimeStamp
    event: Event
    actor_name: str
    location_name: str


@dataclass(frozen=True)
class TerminalReached:
    time: TimeStamp
    terminal_event: str


Signal = TickStarted | WorldEventEmitted | TerminalReached


class SimSink(Protocol):
    def emit(self, signal: Signal) -> None: ...


def make_timestamp(world: WorldState) -> TimeStamp:
    """把 world 当前 tick + calendar 折成 TimeStamp。calendar 缺席时只填 tick。"""
    if world.calendar is None:
        return TimeStamp(tick=world.tick)
    day, phase, tick_in_phase = decompose(world.tick, world.calendar)
    return TimeStamp(
        tick=world.tick,
        scene=SceneStamp(day=day, phase=phase, tick_in_phase=tick_in_phase),
    )
