"""回合引擎:落子(把动作写回世界)+ 最小回合循环。"""
from __future__ import annotations

from society.core.models import Event, WorldState
from society.core.enums import ActionType, Visibility
from society.engine.perception import perceive
from society.agents.brain import decide
from society.agents.memory import remember


def apply_event(world: WorldState, event: Event) -> list[Event]:
    """把一个 event 真正落进世界。返回真正进入 event_log 的事件列表
    (大多数情况是 [event] 本身;MOVE 会展开成 [离场, 到场] 两条)。"""
    match event.type:
        case ActionType.SPEAK | ActionType.THINK:
            world.event_log.append(event)
            return [event]
        case ActionType.PLAN:
            world.agents[event.actor_id].plan = event.content
            world.event_log.append(event)
            return [event]
        case ActionType.MOVE:
            return _apply_move(world, event)
        case ActionType.ACT:
            # 叙述型 ACT:不改任何结构化世界状态,只入 log。
            # 可见性由 perceive() 的 PUBLIC + 同 location 过滤自然覆盖。
            world.event_log.append(event)
            return [event]
    return []


def _apply_move(world: WorldState, event: Event) -> list[Event]:
    """MOVE 落子:写离场事件 → 更新 agent.location_id → 写到场事件。
    brain 给来的原 event 只是「意图」,不入 log。"""
    dest_id = event.destination_id
    if dest_id is None or dest_id not in world.locations:
        return []  # 非法/缺字段:fail-safe 静默丢弃
    agent = world.agents[event.actor_id]
    if dest_id == agent.location_id:
        return []  # 已在目的地,无需移动
    dest = world.locations[dest_id]
    origin_id = agent.location_id

    departure = Event(
        tick=event.tick,
        actor_id=event.actor_id,
        type=ActionType.MOVE,
        content=f"{agent.name} 离开了,去往 {dest.name}",
        location_id=origin_id,
        destination_id=dest_id,
        visibility=Visibility.PUBLIC,
    )
    world.event_log.append(departure)

    agent.location_id = dest_id

    arrival = Event(
        tick=event.tick,
        actor_id=event.actor_id,
        type=ActionType.MOVE,
        content=f"{agent.name} 来到了 {dest.name}",
        location_id=dest_id,
        destination_id=dest_id,
        visibility=Visibility.PUBLIC,
    )
    world.event_log.append(arrival)
    return [departure, arrival]


def render_event(world: WorldState, event: Event) -> None:
    """上帝视角:单行打印一条事件,便于调试扫读。"""
    name = world.agents[event.actor_id].name
    print(f"  {name} [{event.type.value}] {event.content}")


def run_turn(world: WorldState) -> None:
    """一个回合:每个 agent 依次 感知→决策→落子→渲染→沉淀记忆。

    sequential 模型:每人落子后立刻写回 event_log,
    因此后行动者的 perceive 能切到本回合先行动者刚说的 PUBLIC 事件。
    """
    world.tick += 1
    print(f"\n===== tick {world.tick} =====")
    ## 逐人处理:perceive 的边界是"自我上次动作之后",所以先行动者下回合
    ## 自然能在 perception 里捡到后行动者本回合的发言,不需要回合末额外 pass。
    for agent in world.agents.values():
        perception = perceive(world, agent)
        events = decide(perception, world.tick)
        for event in events:
            applied = apply_event(world, event)
            for e in applied:
                render_event(world, e)
        remember(agent, world, perception.visible_events, events)


