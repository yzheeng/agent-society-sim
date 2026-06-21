"""Conductor:模拟的「控制 / 查询」端口,与 stream 的输出端口对称。

引擎只暴露 run_turn(变更)+ Signal/SimSink(输出)。要让任意 UI(CLI / 将来的
TUI / Web)驱动这场戏,需要一个 UI 无关的用例门面,把「导演词汇表」收成方法:

- 推进:step / run_to_terminal —— 手动逐拍 vs 自动跑到终局
- 注入(三个维度,差别在落进哪一层、活多久):
    · inject_fact    客观事实(旁白)——入世界史、公开、在场者感知并记住,永久
    · inject_impulse 冲动——只拨该 agent 的下一次行动,用完即清,只留下后果
    · inject_belief  信念——植入持久私密认知,长留自我、每拍染色,跨重启存活
- 视角:set_god —— 翻动 sink 的心声可见性
- 查询:dossier / agents / locations —— 读私密档案

它持有 (world, director, sink),把控制语义都收在这一处;UI 退化成
「解析输入 → 调一个方法」的薄壳。注意这是用例门面,不是数据搬运层——
查询直接返回现有 dataclass,不另造镜像 DTO。
"""
from __future__ import annotations

from society.core.clock import is_terminal
from society.core.enums import ActionType, Visibility
from society.core.models import Agent, Event, Location, WorldState
from society.engine.director import Director
from society.engine.turn_engine import run_turn
from society.persistence import save_world
from society.stream.signals import SimSink, WorldEventEmitted, make_timestamp


class Conductor:
    def __init__(self, world: WorldState, director: Director, sink: SimSink) -> None:
        self.world = world
        self.director = director
        self.sink = sink

    # —— 推进 ——

    def is_terminal(self) -> bool:
        """下一拍是否已越过终局(与 run_turn 内部判定同一条件)。"""
        cal = self.world.calendar
        return cal is not None and is_terminal(self.world.tick + 1, cal)

    def step(self, k: int = 1) -> None:
        """手动推进 k 拍;碰到终局提前停。每拍落盘。"""
        for _ in range(k):
            if self.is_terminal():
                run_turn(self.world, self.sink, self.director)  # 让引擎发 TerminalReached
                break
            run_turn(self.world, self.sink, self.director)
            save_world(self.world)

    def run_to_terminal(self) -> None:
        """自动模式:一路跑到终局(调用方负责接 KeyboardInterrupt 打断)。"""
        while not self.is_terminal():
            run_turn(self.world, self.sink, self.director)
            save_world(self.world)
        run_turn(self.world, self.sink, self.director)  # 收尾发 TerminalReached

    # —— 注入(三个维度) ——

    def inject_fact(self, location_id: str, content: str) -> None:
        """客观事实(旁白):下一拍在某地点当众发生的世界事件。

        走 director 队列 → 落进 event_log(世界史)→ 在场者感知并沉进各自记忆。
        永久、公开、按地点。
        """
        self.director.inject(location_id, content)

    def inject_impulse(self, agent_id: str, content: str) -> None:
        """冲动:往某 agent 心里塞一瞬间窜起的念头。

        塞进 agent.impulses——只在该 agent【下一次行动】的 prompt 末尾以"突如其来的
        念头"醒目浮现,消费即清,不留存(留下的只是它当拍做出的反应)。
        """
        agent = self.world.agents[agent_id]
        agent.impulses.append(content)
        self._trace_private(agent, f"(一阵冲动莫名窜起){content}")

    def inject_belief(self, agent_id: str, content: str) -> None:
        """信念:往某 agent 植入一条持久私密认知。

        写进 agent.beliefs——从此长留在它的自我里,每拍都在身份段渲染、给行为染色,
        且随 agent 落盘跨重启存活,直到被显式抹去。
        """
        agent = self.world.agents[agent_id]
        agent.beliefs.append(content)
        self._trace_private(agent, f"(一个认定在心里扎下了根){content}")
        save_world(self.world)

    def _trace_private(self, agent: Agent, content: str) -> None:
        """给一次私密注入(冲动/信念)留一条 PRIVATE 事件痕:入 event_log + 发给 sink。
        是上帝视角 / 回放的留痕,不参与该 agent 的感知。"""
        event = Event(
            tick=self.world.tick,
            actor_id=agent.id,
            type=ActionType.THINK,
            content=content,
            location_id=agent.location_id,
            visibility=Visibility.PRIVATE,
        )
        self.world.event_log.append(event)
        self.sink.emit(WorldEventEmitted(
            time=make_timestamp(self.world),
            event=event,
            actor_name=agent.name,
            location_name=self.world.locations[agent.location_id].name,
        ))

    # —— 视角 ——

    def set_god(self, on: bool) -> None:
        """翻动 sink 的上帝视角。仅对实现了 god 属性的 sink 生效。"""
        setattr(self.sink, "god", on)

    def god(self) -> bool:
        return bool(getattr(self.sink, "god", False))

    # —— 查询(直接返回 domain dataclass,不造镜像 DTO) ——

    def agents(self) -> list[Agent]:
        return list(self.world.agents.values())

    def locations(self) -> list[Location]:
        return list(self.world.locations.values())

    def dossier(self, agent_id: str) -> Agent:
        return self.world.agents[agent_id]
