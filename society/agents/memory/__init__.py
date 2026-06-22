"""agent 记忆子系统。

对外只暴露这层 facade,内部结构(工作/语义/压缩/召回……)可以自由演化,
调用方只认 remember / recall / maybe_compress 三个入口。

- working:     工作记忆 = 第一人称经历流(情景内容)
- compression: 经历流超阈值时滚动压成梗概,兜底物理长度
- reflection:  周期性把情景经历蒸馏成持久信念(belief)= 语义记忆的生成引擎

后续规划(打分召回 / 可检索长期情景库)在此包内新增模块,facade 按需扩。
"""
from __future__ import annotations

from society.agents.memory.working import remember, recall
from society.agents.memory.compression import maybe_compress
from society.agents.memory.reflection import maybe_reflect

__all__ = ["remember", "recall", "maybe_compress", "maybe_reflect"]
