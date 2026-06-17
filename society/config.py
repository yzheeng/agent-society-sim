"""运行时配置:从项目根目录的 config.json 读,解析成 frozen dataclass。

调用约定:
- 所有消费方走 `load_config()`,首次调用读盘并缓存,后续直接拿缓存
- 缺字段直接让 dataclass 构造抛 TypeError,fail-fast
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LLMConfig:
    model: str
    base_url: str
    api_key_env: str


@dataclass(frozen=True)
class MemoryConfig:
    recall_window: int


@dataclass(frozen=True)
class SimulationConfig:
    num_turns: int


@dataclass(frozen=True)
class PersistenceConfig:
    enabled: bool
    data_dir: str   # 相对项目根


@dataclass(frozen=True)
class Config:
    llm: LLMConfig
    memory: MemoryConfig
    simulation: SimulationConfig
    persistence: PersistenceConfig


_DEFAULT_PATH = Path(__file__).parent.parent / "config.json"
_cached: Config | None = None


def load_config(path: Path | None = None) -> Config:
    """读取并缓存 config.json。默认从项目根目录读。"""
    global _cached
    if _cached is not None and path is None:
        return _cached

    raw = json.loads((path or _DEFAULT_PATH).read_text(encoding="utf-8"))
    config = Config(
        llm=LLMConfig(**raw["llm"]),
        memory=MemoryConfig(**raw["memory"]),
        simulation=SimulationConfig(**raw["simulation"]),
        persistence=PersistenceConfig(**raw["persistence"]),
    )
    if path is None:
        _cached = config
    return config
