"""回合引擎:落子(把动作写回世界)+ 最小回合循环。"""
from __future__ import annotations

from society.core.models import Event, WorldState
from society.core.enums import ActionType
from society.engine.perception import perceive
from society.agents.brain import decide


def apply_event(world: WorldState, event: Event) -> None:
    """把一个event真正落进世界"""
    world.event_log.append(event)
    match event.type:
        case ActionType.SPEAK | ActionType.THINK:
            pass
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
    """一个回合:每个 agent 依次 感知→决策→落子→渲染。"""
    world.tick += 1
    print(f"\n===== tick {world.tick} =====")

    for agent in world.agents.values():
        perception = perceive(world, agent)        # 看见
        event = decide(perception, world.tick)     # 决定
        apply_event(world, event)                  # 落子，影响世界
        render_event(event)                        # 上帝视角输出


