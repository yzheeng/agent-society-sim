"""回合引擎:落子(把动作写回世界)+ 最小回合循环。"""
from __future__ import annotations

from society.core.models import Event, WorldState
from society.core.enums import ActionType
from society.engine.perception import perceive
from society.agents.brain import decide
from society.agents.memory import remember


def apply_event(world: WorldState, event: Event) -> None:
    """把一个event真正落进世界"""
    world.event_log.append(event)
    match event.type:
        case ActionType.SPEAK | ActionType.THINK:
            pass
        case ActionType.PLAN:
            world.agents[event.actor_id].plan = event.content
        case ActionType.MOVE:
            # TODO
            pass
        case ActionType.ACT:
            # TODO
            pass

def render_event(event: Event) -> None:
    """上帝视角"""
    god_mark = "  〔心声·仅上帝可见〕" if event.visibility.value == "private" else ""
    print(f"  tick{event.tick}  {event.actor_id} [{event.type.value}]{god_mark}")
    print(f"       {event.content}")


def run_turn(world: WorldState) -> None:
    """一个回合:每个 agent 依次 感知→决策→落子→渲染→沉淀记忆。

    sequential 模型:每人落子后立刻写回 event_log,
    因此后行动者的 perceive 能切到本回合先行动者刚说的 PUBLIC 事件。
    """
    world.tick += 1
    print(f"\n===== tick {world.tick} =====")
    ## 逐人处理
    for agent in world.agents.values():
        perception = perceive(world, agent)
        events = decide(perception, world.tick)
        for event in events:
            apply_event(world, event)
            render_event(event)
        remember(agent, world, perception.visible_events, events)


