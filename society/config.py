"""运行时配置:从项目根目录的 config.json 读,解析成 frozen dataclass。

调用约定:
- 所有消费方走 `load_config()`,首次调用读盘并缓存,后续直接拿缓存
- 缺字段直接让 dataclass 构造抛 TypeError,fail-fast
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LLMProfile:
    model: str
    base_url: str
    api_key_env: str | None = None  # 本地模型(如 LM Studio)可省略
    # 透传给 chat.completions.create 的采样参数(temperature / top_p / presence_penalty / max_tokens 等)。
    # 不同 profile 各管各的:本地小模型要压复读,远端 SaaS 用默认就行。
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMConfig:
    active: str
    profiles: dict[str, LLMProfile]

    def current(self) -> LLMProfile:
        if self.active not in self.profiles:
            raise ValueError(
                f"llm.active='{self.active}' 不在 profiles 里,可选: {list(self.profiles)}"
            )
        return self.profiles[self.active]


@dataclass(frozen=True)
class CompressionConfig:
    trigger_size: int   # memory 长到这个数就触发一次压缩
    keep_recent: int    # 压缩后保留最近多少条原文不压


@dataclass(frozen=True)
class MemoryConfig:
    compression: CompressionConfig


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
        llm=LLMConfig(
            active=raw["llm"]["active"],
            profiles={
                name: LLMProfile(**p) for name, p in raw["llm"]["profiles"].items()
            },
        ),
        memory=MemoryConfig(
            compression=CompressionConfig(**raw["memory"]["compression"]),
        ),
        simulation=SimulationConfig(**raw["simulation"]),
        persistence=PersistenceConfig(**raw["persistence"]),
    )
    if path is None:
        _cached = config
    return config
