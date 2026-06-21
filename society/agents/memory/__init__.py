"""agent 记忆子系统。

对外只暴露这层 facade,内部结构(情景/语义/压缩/召回……)可以自由演化,
调用方只认 remember / recall / maybe_compress 三个入口。

- episodic:    情景记忆 = 第一人称经历流(当前唯一的记忆类型)
- compression: 经历流超阈值时滚动压成梗概,兜底物理长度

后续规划(语义记忆 / 反思 belief / 打分召回)在此包内新增模块,facade 按需扩。
"""
from __future__ import annotations

from society.agents.memory.episodic import remember, recall
from society.agents.memory.compression import maybe_compress

__all__ = ["remember", "recall", "maybe_compress"]
