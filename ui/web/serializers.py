"""把引擎的 Signal / domain dataclass 序列化成前端可消费的 JSON dict。

这层只住在 ui/web 里、只服务 web sink —— core 与 conductor 一行不动,
守住"引擎只认通用结构"的红线。产出统一带一个 `kind` 标签,前端据此分支渲染。

god 视角的处置:后端把 PUBLIC / PRIVATE 事件都推下去,在每条 event 上带
`visibility` 字段,由前端决定"内心图层"显不显 —— 把 CLI 那个全局二选一的
god 开关,降解成前端可随时叠加的渲染图层。
"""
from __future__ import annotations

from society.core.models import Agent, Location
from society.stream.signals import (
    Signal,
    TickStarted,
    TimeStamp,
    WorldEventEmitted,
    TerminalReached,
)


def time_to_dict(time: TimeStamp) -> dict:
    """TimeStamp → dict。calendar 缺席时 scene 为 None。"""
    scene = None
    if time.scene is not None:
        scene = {
            "day": time.scene.day,
            "phase": time.scene.phase,
            "tick_in_phase": time.scene.tick_in_phase,
        }
    return {"tick": time.tick, "scene": scene}


def signal_to_dict(signal: Signal) -> dict:
    """把一个 Signal 折成带 kind 标签的扁平 dict。

    - tick     :一拍开始。仅 time。
    - event    :一条已落子的 in-world 事件。event 复用 Event.to_dict,
                 额外带解析好的 actor_name / location_name。
    - terminal :剧情终局。
    """
    match signal:
        case TickStarted(time):
            return {"kind": "tick", "time": time_to_dict(time)}
        case WorldEventEmitted(time, event, actor_name, location_name):
            return {
                "kind": "event",
                "time": time_to_dict(time),
                "actor_name": actor_name,
                "location_name": location_name,
                "event": event.to_dict(),
            }
        case TerminalReached(time, terminal_event):
            return {
                "kind": "terminal",
                "time": time_to_dict(time),
                "terminal_event": terminal_event,
            }
    raise TypeError(f"未知 Signal 类型:{type(signal)!r}")


def location_to_dict(loc: Location) -> dict:
    """地点摘要(列表用)。直接借 domain 自带的 to_dict。"""
    return loc.to_dict()


def agent_brief(agent: Agent) -> dict:
    """角色公开摘要 —— 列表 / 地点聚类用,不含私密层。"""
    return {
        "id": agent.id,
        "name": agent.name,
        "location_id": agent.location_id,
        "public_persona": agent.public_persona,
    }


def agent_dossier(agent: Agent) -> dict:
    """角色完整档案(上帝视角)—— 含私密层 / 信念 / 关系 / 印象 / 近期记忆。

    直接借 Agent.to_dict(它本就为持久化序列化全字段),额外补上不持久化的
    impulses(转瞬冲动),供观察台看"待发的冲动"。
    """
    d = agent.to_dict()
    d["impulses"] = list(agent.impulses)
    return d
