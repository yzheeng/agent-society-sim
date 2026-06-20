"""时间结构:把单调递增的 tick 翻译成"第几天的哪个时段"。

day → phase → tick 三层:
- day:剧本的"幕"。total_days 决定整个剧情的总长。
- phase:一天里的有戏剧色彩的时段(早间/午间/放学后/夜晚),
       phase 名本身就是 prompt 渲染时的"时段感"。
- tick:引擎最小拍。一个 phase 包含 ticks_per_phase 个 tick——
       即同一时段内的 N 轮对话,所有在场 agent 各动一次为一轮。

约束:tick 从 1 开始(run_turn 是先 tick += 1 再处理),所以
decompose 用 (tick - 1) 做整除。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Calendar:
    total_days: int
    phases: list[str]            # 顺序即时间顺序,如 ["早间", "午间", "放学后", "夜晚"]
    ticks_per_phase: int
    terminal_event: str          # 截止那一刻发生的事,如 "文化祭开幕"


def total_ticks(cal: Calendar) -> int:
    return cal.total_days * len(cal.phases) * cal.ticks_per_phase


def decompose(tick: int, cal: Calendar) -> tuple[int, str, int]:
    """tick(1-based)→(day_1based, phase_name, tick_in_phase_1based)。

    超出 total_ticks 时返回最后一拍的三元组(由 is_terminal 兜底,不在此处抛)。
    """
    idx = max(0, min(tick - 1, total_ticks(cal) - 1))
    ticks_per_day = len(cal.phases) * cal.ticks_per_phase
    day = idx // ticks_per_day + 1
    in_day = idx % ticks_per_day
    phase_index = in_day // cal.ticks_per_phase
    tick_in_phase = in_day % cal.ticks_per_phase + 1
    return day, cal.phases[phase_index], tick_in_phase


def days_remaining(tick: int, cal: Calendar) -> int:
    """从"此刻"看,terminal_event 还有几天到来。当前正在过的那天算 0。"""
    day, _, _ = decompose(tick, cal)
    return max(0, cal.total_days - day)


def is_terminal(tick: int, cal: Calendar) -> bool:
    """tick 已经走完所有可用拍数,terminal_event 应已发生。"""
    return tick > total_ticks(cal)
