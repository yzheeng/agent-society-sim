"""CLISink:把 Signal 渲染成命令行单行,作为最简的上帝视角输出。

格式骨架:
  - tick 标题:`===== tick N · Day D · phase (k) =====`(calendar 缺席时退化为 `===== tick N =====`)
  - 事件行  :`  {actor} @{location} [{type}] {content}`
  - 终局    :`[终局] {terminal_event}`

god 开关:关闭时只渲染台面上的言行(PUBLIC——speak / act / move),
滤掉心声与盘算(PRIVATE——think / plan)。开关由 Conductor.set_god 在运行时翻动。
"""
from __future__ import annotations

from society.core.enums import Visibility
from society.stream.signals import (
    Signal,
    TickStarted,
    WorldEventEmitted,
    TerminalReached,
)


class CLISink:
    def __init__(self, god: bool = False) -> None:
        self.god = god  # True:连心声/plan 一起显示;False:只显台面言行

    def emit(self, signal: Signal) -> None:
        match signal:
            case TickStarted(time):
                if time.scene is not None:
                    tag = f" · Day {time.scene.day} · {time.scene.phase} ({time.scene.tick_in_phase})"
                else:
                    tag = ""
                print(f"\n===== tick {time.tick}{tag} =====")
            case WorldEventEmitted(_, event, actor_name, location_name):
                if not self.god and event.visibility == Visibility.PRIVATE:
                    return  # 非上帝视角:藏掉心声 / 盘算
                print(f"  {actor_name} @{location_name} [{event.type.value}] {event.content}")
            case TerminalReached(_, terminal_event):
                print(f"\n[终局] {terminal_event}")
