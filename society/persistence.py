"""状态持久化:让 agent 跨进程重启保留剧情。

三层文件(布局见 data/):
- data/world.json      —— 元状态 (tick / deadline / locations),overwrite per turn
- data/events.jsonl    —— 全量事件流 (source of truth),append-only
- data/agents/{id}.json —— 单个 agent 完整状态 (含 memory / plan / relationships)

调用约定:
- 主循环每回合末调 save_world(world)
- 启动时 load_world() 返回 WorldState | None;None 表示无存档,走场景初始化

MVP 接受弱一致性:写盘半途崩溃可能让 events.jsonl 比 world.json 超前一回合,
load 时按 world.tick 截断并 WARN。崩溃强一致性是后续。
单进程假设:_last_persisted_count 是模块级状态。
"""
from __future__ import annotations

import json
from pathlib import Path

from society.config import load_config
from society.core.models import Agent, Event, Location, WorldState


_PROJECT_ROOT = Path(__file__).parent.parent


def _root() -> Path:
    return _PROJECT_ROOT / load_config().persistence.data_dir


def _world_file() -> Path:
    return _root() / "world.json"


def _events_file() -> Path:
    return _root() / "events.jsonl"


def _agents_dir() -> Path:
    return _root() / "agents"


# 模块级:上次落盘时 event_log 的长度,用于 diff append
_last_persisted_count: int = 0


def save_world(world: WorldState) -> None:
    if not load_config().persistence.enabled:
        return
    _ensure_dirs()
    _append_new_events(world)
    _atomic_write_json(_world_file(), world.to_meta_dict())
    for agent in world.agents.values():
        _validate_id(agent.id)
        _atomic_write_json(_agents_dir() / f"{agent.id}.json", agent.to_dict())


def load_world() -> WorldState | None:
    if not _all_files_present():
        return None

    meta = json.loads(_world_file().read_text(encoding="utf-8"))
    locations = {lid: Location.from_dict(l) for lid, l in meta["locations"].items()}

    agents: dict[str, Agent] = {}
    for path in sorted(_agents_dir().glob("*.json")):
        a = Agent.from_dict(json.loads(path.read_text(encoding="utf-8")))
        agents[a.id] = a

    event_log = [
        Event.from_dict(json.loads(line))
        for line in _events_file().read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    world_tick = meta["tick"]
    # 半崩溃容错:events 比 world.tick 超前 → 截断未确认的尾巴
    if event_log and event_log[-1].tick > world_tick:
        kept = [e for e in event_log if e.tick <= world_tick]
        dropped = len(event_log) - len(kept)
        print(
            f"[persistence] WARN: 截断 {dropped} 条超前 events "
            f"(world.tick={world_tick}, max event tick={event_log[-1].tick})"
        )
        _rewrite_events(kept)
        event_log = kept

    global _last_persisted_count
    _last_persisted_count = len(event_log)

    return WorldState(
        tick=world_tick,
        agents=agents,
        locations=locations,
        event_log=event_log,
    )


def _all_files_present() -> bool:
    return (
        _world_file().exists()
        and _events_file().exists()
        and _agents_dir().is_dir()
        and any(_agents_dir().glob("*.json"))
    )


def _ensure_dirs() -> None:
    _root().mkdir(parents=True, exist_ok=True)
    _agents_dir().mkdir(exist_ok=True)


def _append_new_events(world: WorldState) -> None:
    global _last_persisted_count
    assert _last_persisted_count <= len(world.event_log), \
        f"event_log 被外部缩短: {_last_persisted_count} > {len(world.event_log)}"
    new = world.event_log[_last_persisted_count:]
    if not new:
        return
    with _events_file().open("a", encoding="utf-8") as f:
        for e in new:
            f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
    _last_persisted_count = len(world.event_log)


def _rewrite_events(events: list[Event]) -> None:
    """全量重写 events.jsonl,用于 load 时截断超前事件后与磁盘对齐。"""
    tmp = _events_file().with_suffix(_events_file().suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
    tmp.replace(_events_file())


def _atomic_write_json(path: Path, obj: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _validate_id(agent_id: str) -> None:
    assert "/" not in agent_id and "\\" not in agent_id and ".." not in agent_id, \
        f"非法 agent id(含路径分隔符): {agent_id!r}"
