"""场景加载:从 content/scenarios/*.yaml 读取纯数据,校验后组装成 WorldState。

设计取舍
- 场景是【人工编写的内容】,不是代码。所以用 YAML(多行 prose 友好、可注释),
  而不是把角色写死在 .py 里。换文案 / 加角色 / 替场景都不用碰代码。
- 格式只是序列化细节,真正的工程在【加载即校验】:location_id 指向不存在的地点、
  relationships 拼错的 key、缺字段……都在这里大声报错,而不是跑到一半才静默出问题。

对外只暴露 list_scenarios() 和 load_scenario(name)。
"""
from __future__ import annotations

from pathlib import Path

import yaml

from society.core.clock import Calendar
from society.core.models import Agent, Location, WorldState

_SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"


def list_scenarios() -> list[str]:
    """列出所有可用场景名(= scenarios/ 下 .yaml 文件名去掉后缀)。"""
    return sorted(p.stem for p in _SCENARIO_DIR.glob("*.yaml"))


def load_scenario(name: str) -> WorldState:
    """按名加载场景,校验通过后返回挂好 calendar 的 WorldState。

    name 不带后缀,例如 load_scenario("sample") 读 scenarios/sample.yaml。
    任何结构 / 引用问题都抛 ValueError,信息里带场景名,便于定位是哪份配置写坏了。
    """
    path = _SCENARIO_DIR / f"{name}.yaml"
    if not path.exists():
        available = ", ".join(list_scenarios()) or "(空)"
        raise ValueError(f"找不到场景「{name}」({path})。可用场景:{available}")

    with path.open("r", encoding="utf-8") as f:
        # safe_load:只认纯数据,杜绝 YAML 反序列化执行任意对象的坑。
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError(f"场景「{name}」顶层必须是映射(calendar / locations / agents)。")

    calendar = _build_calendar(name, data.get("calendar"))
    locations = _build_locations(name, data.get("locations"))
    agents = _build_agents(name, data.get("agents"), locations)

    return WorldState(agents=agents, locations=locations, calendar=calendar)


def _build_calendar(name: str, raw: object) -> Calendar:
    if not isinstance(raw, dict):
        raise ValueError(f"场景「{name}」缺少 calendar 段或格式不对。")
    for key in ("total_days", "phases", "ticks_per_phase", "terminal_event"):
        if key not in raw:
            raise ValueError(f"场景「{name}」calendar 缺字段:{key}")
    phases = raw["phases"]
    if not isinstance(phases, list) or not phases:
        raise ValueError(f"场景「{name}」calendar.phases 必须是非空列表。")
    if not isinstance(raw["total_days"], int) or raw["total_days"] <= 0:
        raise ValueError(f"场景「{name}」calendar.total_days 必须是正整数。")
    if not isinstance(raw["ticks_per_phase"], int) or raw["ticks_per_phase"] <= 0:
        raise ValueError(f"场景「{name}」calendar.ticks_per_phase 必须是正整数。")
    return Calendar(
        total_days=raw["total_days"],
        phases=list(phases),
        ticks_per_phase=raw["ticks_per_phase"],
        terminal_event=str(raw["terminal_event"]),
    )


def _build_locations(name: str, raw: object) -> dict[str, Location]:
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"场景「{name}」缺少 locations 段或为空。")
    locations: dict[str, Location] = {}
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or "id" not in item or "name" not in item:
            raise ValueError(f"场景「{name}」第 {i+1} 个 location 缺 id / name。")
        loc = Location.from_dict(item)
        if loc.id in locations:
            raise ValueError(f"场景「{name}」location id 重复:{loc.id}")
        locations[loc.id] = loc
    return locations


def _build_agents(
    name: str, raw: object, locations: dict[str, Location]
) -> dict[str, Agent]:
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"场景「{name}」缺少 agents 段或为空。")
    agents: dict[str, Agent] = {}
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"场景「{name}」第 {i+1} 个 agent 不是映射。")
        try:
            agent = Agent.from_dict(item)
        except KeyError as e:
            raise ValueError(f"场景「{name}」第 {i+1} 个 agent 缺字段:{e}") from e
        if agent.id in agents:
            raise ValueError(f"场景「{name}」agent id 重复:{agent.id}")
        if agent.location_id not in locations:
            raise ValueError(
                f"场景「{name}」agent「{agent.id}」的 location_id="
                f"{agent.location_id} 不存在于 locations。"
            )
        agents[agent.id] = agent

    # relationships 的引用完整性:必须指向真实存在的 agent,且不能指向自己。
    for agent in agents.values():
        for other_id in agent.relationships:
            if other_id not in agents:
                raise ValueError(
                    f"场景「{name}」agent「{agent.id}」的 relationships 指向"
                    f"不存在的 agent:{other_id}"
                )
            if other_id == agent.id:
                raise ValueError(
                    f"场景「{name}」agent「{agent.id}」的 relationships 不能指向自己。"
                )
    return agents
