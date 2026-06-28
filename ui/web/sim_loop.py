"""SimLoop:在后台线程里按节奏推进模拟的运行控制器。

为什么要后台线程:`run_turn` 是同步阻塞的(顺序等每个 agent 的 LLM 往返),
绝不能塞进 asyncio 事件循环 —— 会把 websocket 一起卡死。于是模拟跑在独立线程,
事件循环那侧只管广播。

控制语义(run / pause / step)只翻标志位,由循环在【两拍之间】读取并据此行动:
- run   :自动连跑到终局
- pause :停在当前拍跑完之后(LLM 阻塞不可中断,无法 token 级急停 —— 这是同步引擎的代价)
- step k:补充 k 拍预算,跑完回到空闲

空闲时线程 wait 在一个 Event 上(不忙等),被 run / step 唤醒。
"""
from __future__ import annotations

import threading

from society.conductor import Conductor


class SimLoop:
    def __init__(self, conductor: Conductor) -> None:
        self.c = conductor
        self._lock = threading.Lock()
        self._running = False       # 自动连跑
        self._step_budget = 0       # 待执行的手动步数
        self._stop = False          # 关闭信号
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="sim-loop", daemon=True)

    def start(self) -> None:
        self._thread.start()

    # —— 控制入口(从 asyncio 线程调用,只翻标志位,瞬时返回) ——

    def run(self) -> None:
        """自动连跑到终局。"""
        with self._lock:
            self._running = True
        self._wake.set()

    def pause(self) -> None:
        """停止推进 —— 在当前正在跑的那一拍结束后生效。"""
        with self._lock:
            self._running = False
            self._step_budget = 0

    def step(self, k: int = 1) -> None:
        """补充 k 拍预算,跑完即停。"""
        with self._lock:
            self._step_budget += max(1, k)
        self._wake.set()

    def stop(self) -> None:
        """关闭后台线程(进程退出时调用)。"""
        self._stop = True
        self._wake.set()

    def status(self) -> dict:
        """当前运行态快照,供 REST 查询。"""
        with self._lock:
            return {
                "running": self._running,
                "step_budget": self._step_budget,
                "tick": self.c.world.tick,
                "terminal": self.c.is_terminal(),
            }

    # —— 后台线程主体 ——

    def _loop(self) -> None:
        while not self._stop:
            with self._lock:
                go = self._running or self._step_budget > 0
            if not go:
                self._wake.wait(timeout=1.0)   # 空闲挂起,被 run / step 唤醒
                self._wake.clear()
                continue

            if self.c.is_terminal():
                # 终局:让引擎发一次 TerminalReached,然后停下自动 / 清空预算,
                # 避免空转狂发终局信号。
                self.c.step(1)
                with self._lock:
                    self._running = False
                    self._step_budget = 0
                continue

            # 真正的一拍:阻塞、慢,期间引擎经 sink 持续 emit signal。
            self.c.step(1)
            with self._lock:
                if self._step_budget > 0:
                    self._step_budget -= 1
