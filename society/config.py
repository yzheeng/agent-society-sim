"""运行时配置:从项目根目录的 config.json 读,解析成 frozen dataclass。

调用约定:
- 所有消费方走 `load_config()`,首次调用读盘并缓存,后续直接拿缓存
- 缺字段直接让 dataclass 构造抛 TypeError,fail-fast
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# 加载 .env,确保下面的 ${VAR} 占位符解析能拿到真实值。
# 与 llm/client.py 各自调一次,load_dotenv 幂等、互不影响,谁先 import 都不漏。
load_dotenv()

# config.json 里凡是 "${VAR}" 形式的字符串,都从环境变量(.env)取真实值。
# 这样 model / base_url / api_key 这类会换的东西只存在 .env,config.json 只留引用。
_ENV_REF = re.compile(r"\$\{([^}]+)\}")


def _resolve_env(obj: Any) -> Any:
    """递归把 config 里的 ${VAR} 占位符替换成 .env 中的真实值,缺值即 fail-fast。"""
    if isinstance(obj, str):
        def _sub(m: re.Match[str]) -> str:
            name = m.group(1)
            val = os.environ.get(name)
            if val is None:
                raise RuntimeError(
                    f"config 引用了环境变量 {name},但 .env / 环境里没有,请在项目根目录的 .env 里设置"
                )
            return val
        return _ENV_REF.sub(_sub, obj)
    if isinstance(obj, dict):
        return {k: _resolve_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env(v) for v in obj]
    return obj


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
class ReflectionConfig:
    interval: int       # 每隔多少拍反思一次(tick % interval == 0 触发;<=0 关闭)
    max_beliefs: int    # 反思后 beliefs 封顶条数,防无限增长


@dataclass(frozen=True)
class MemoryConfig:
    compression: CompressionConfig
    reflection: ReflectionConfig


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
    raw = _resolve_env(raw)
    config = Config(
        llm=LLMConfig(
            active=raw["llm"]["active"],
            profiles={
                name: LLMProfile(**p) for name, p in raw["llm"]["profiles"].items()
            },
        ),
        memory=MemoryConfig(
            compression=CompressionConfig(**raw["memory"]["compression"]),
            reflection=ReflectionConfig(**raw["memory"]["reflection"]),
        ),
        simulation=SimulationConfig(**raw["simulation"]),
        persistence=PersistenceConfig(**raw["persistence"]),
    )
    if path is None:
        _cached = config
    return config
