"""回合引擎:落子(把动作写回世界)+ 最小回合循环。"""
from __future__ import annotations

from society.core.models import Event, WorldState
from society.core.enums import ActionType, Visibility
from society.core.clock import is_terminal
from society.engine.perception import perceive
from society.engine.director import Director
from society.agents.brain import decide
from society.agents.memory import remember, maybe_compress, maybe_reflect
from society.stream.signals import (
    SimSink,
    TickStarted,
    WorldEventEmitted,
    TerminalReached,
    make_timestamp,
)


def apply_event(world: WorldState, event: Event) -> list[Event]:
    """把一个 event 真正落进世界。返回真正进入 event_log 的事件列表
    (大多数情况是 [event] 本身;MOVE 会展开成 [离场, 到场] 两条)。"""
    match event.type:
        case ActionType.SPEAK | ActionType.THINK | ActionType.SILENCE:
            # SILENCE 是 PUBLIC 的外显姿态:落进 log,可见性交给 perceive 的
            # PUBLIC + 同 location 过滤,让在场者察觉"这人没作声"。
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


def run_turn(world: WorldState, sink: SimSink, director: Director | None = None) -> None:
    """一个回合:(导演注入火种 →)每个 agent 依次 感知→决策→落子→发信号→沉淀记忆。

    sequential 模型:每人落子后立刻写回 event_log,
    因此后行动者的 perceive 能切到本回合先行动者刚说的 PUBLIC 事件。

    director 在 tick 自增后、所有 agent 行动前注入外部火种:火种作为 PUBLIC 事件
    先落进 event_log,本回合在场 agent 的 perceive 就能把它当"此刻"拾到。

    若 calendar 已走到终局,直接发 TerminalReached 并返回——不再推进 tick、不再决策。
    """
    if world.calendar is not None and is_terminal(world.tick + 1, world.calendar):
        sink.emit(TerminalReached(
            time=make_timestamp(world),
            terminal_event=world.calendar.terminal_event,
        ))
        return
    world.tick += 1
    sink.emit(TickStarted(time=make_timestamp(world)))

    if director is not None:
        for event in director.sparks_for(world):
            world.event_log.append(event)
            sink.emit(WorldEventEmitted(
                time=make_timestamp(world),
                event=event,
                actor_name="旁白",
                location_name=world.locations[event.location_id].name,
            ))

    ## 逐人处理:perceive 的边界是"自我上次动作之后",所以先行动者下回合
    ## 自然能在 perception 里捡到后行动者本回合的发言,不需要回合末额外 pass。
    for agent in world.agents.values():
        perception = perceive(world, agent)
        events = decide(perception, world.tick)
        for event in events:
            applied = apply_event(world, event)
            for e in applied:
                sink.emit(WorldEventEmitted(
                    time=make_timestamp(world),
                    event=e,
                    actor_name=world.agents[e.actor_id].name,
                    location_name=world.locations[e.location_id].name,
                ))
        remember(agent, world, perception.visible_events, events)
        # 反思在压缩之前:趁记忆被溶解前,从最丰富的那版经历里蒸馏信念。
        maybe_reflect(agent, world)
        maybe_compress(agent)


