"""Perception:世界喂给单个 agent 的【感官输入契约】。

它是"此刻这个 agent 能看见 / 知道什么"的一帧快照,与 society.stream 里
"引擎喂给 UI 的输出契约"(Signal)对称——一个是世界 → agent 的入口,一个是
引擎 → UI 的出口。两者都属于跨层边界,所以都放在底层、谁都能依赖的位置:
输出契约在 stream,输入契约在 core。

之所以放 core(而非 engine):agents 层(brain / prompts / tools)只消费这个
【类型】,从不调用装配它的 perceive() 函数;装配逻辑留在 engine.perception。
把类型沉到 core,agents 就不必反向依赖 engine,依赖图保持单向。

注意它只是一帧派生视图,不是持久实体——所以不放 models.py,也没有 to_dict。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from society.core.clock import Calendar
from society.core.models import Agent, Event, Location


@dataclass
class Perception:
    self_agent: Agent              # 它自己(私密层在这里面:goal / secret / plan)
    visible_events: list[Event] = field(default_factory=list)  # 它能看见的公开事件
    others_present: list[Agent] = field(default_factory=list)  # 同地点还有谁在场
    location_catalog: dict[str, Location] = field(default_factory=dict)  # 我此刻知道还能去的地方
    calendar: Calendar | None = None   # 世界时间结构(prompt 层负责翻译成时段感)
    tick: int = 0                  # 当前 tick,配合 calendar 推导"今天是第几天/哪个时段"
