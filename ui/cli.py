"""CLISink:把 Signal 渲染成命令行单行,作为最简的上帝视角输出。

格式骨架沿用旧 print:
  - tick 标题:`===== tick N · Day D · phase (k) =====`(calendar 缺席时退化为 `===== tick N =====`)
  - 事件行  :`  {actor} @{location} [{type}] {content}`
  - 终局    :`[终局] {terminal_event}`
"""
from __future__ import annotations

from society.stream.signals import (
    Signal,
    TickStarted,
    WorldEventEmitted,
    TerminalReached,
)


class CLISink:
    def emit(self, signal: Signal) -> None:
        match signal:
            case TickStarted(time):
                if time.scene is not None:
                    tag = f" · Day {time.scene.day} · {time.scene.phase} ({time.scene.tick_in_phase})"
                else:
                    tag = ""
                print(f"\n===== tick {time.tick}{tag} =====")
            case WorldEventEmitted(_, event, actor_name, location_name):
                print(f"  {actor_name} @{location_name} [{event.type.value}] {event.content}")
            case TerminalReached(_, terminal_event):
                print(f"\n[终局] {terminal_event}")
