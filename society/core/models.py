"""社会模拟 · 核心数据模型(第一步 / MVP)

设计原则:引擎只认识下面这些【通用】结构;具体"主题"(人物、地点)
都是喂进来的【数据】。将来想换世界观,只替换文件最底下的数据部分,
上面的引擎代码一行都不用动。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .enums import ActionType, Visibility

@dataclass
class Location:
    id: str
    name: str
    description: str = ""

@dataclass
class Event:
    """世界里发生的一件事。整条 event_log 就是这个世界的全部历史,
    也是 TUI 渲染、感知过滤、复现回放共同的数据来源。"""
    tick: int                  # 第几回合发生
    actor_id: str              # 谁触发的
    type: ActionType
    content: str               # 说了 / 做了 / 想了什么
    location_id: str           # 在哪儿发生
    targets: list[str] = field(default_factory=list)      # 指向谁(可空)
    visibility: Visibility = Visibility.PUBLIC


@dataclass
class Agent:
    """一个角色。注意公开层和私密层是【分开】存的 ——
    这道分隔正是后面感知过滤、以及'嘴上一套心里一套'戏剧性的来源。"""
    id: str
    name: str
    location_id: str

    # —— 公开层:别人能看到的 ——
    public_persona: str

    # —— 私密层:只有它自己 + 上帝知道 ——
    private_goal: str          # 它真正想要的
    secret: str                # 被戳破会出事的东西
    plan: str = ""             # 当前短期打算,每回合可更新

    # —— 关系:对其他 agent 的好感 / 信任,-100..100 —— 这就是"摩擦"的量化
    relationships: dict[str, int] = field(default_factory=dict)

    # —— 记忆:先用最朴素的字符串列表,跑通后再升级成你那套短/长期记忆 ——
    memory: list[str] = field(default_factory=list)

@dataclass
class WorldState:
    """整个世界的唯一事实来源。"""
    tick: int = 0
    days_until_deadline: int = 7
    agents: dict[str, Agent] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    event_log: list[Event] = field(default_factory=list)

    def agents_at(self, location_id: str) -> list[Agent]:
        """某地点此刻在场的 agent —— 下一步的感知过滤会用到它。"""
        return [a for a in self.agents.values() if a.location_id == location_id]
