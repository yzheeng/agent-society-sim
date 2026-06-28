"""SimLoop:在后台线程里按节奏推进模拟的运行控制器。

为什么要后台线程:`run_turn` 是同步阻塞的(顺序等每个 agent 的 LLM 往返),
绝不能塞进 asyncio 事件循环 —— 会把 websocket 一起卡死。于是模拟跑在独立线程,
事件循环那侧只管广播。

控制语义(run / pause / step)只翻标志位,由循环在【两拍之间】读取并据此行动:
- run   :自动连跑到终局
- pause :停在当前拍跑完之后(LLM 阻塞不可中断,无法 token 级急停 —— 这是同步引擎的代价)
- step k:补充 k 拍预算,跑完回到空闲

空闲时线程 wait 在一个 Event 上(不忙等),被 run / step / submit 唤醒。

## 操作队列(注入等 world 写入的归口)

注入(inject_fact/impulse/belief)会改 world,inject_belief 还会 save_world——
而后台线程每拍也 save_world,两边并发写盘 + 共享模块级游标会出事。解法:让所有
对 world 的写入都【只】发生在这个后台线程。asyncio 端经 submit() 把操作排进队列,
线程在每轮循环顶部(拍间)drain 执行。submit 返回 concurrent.futures.Future,
调用方可 asyncio.wrap_future 等它落定,拿到即时反馈。
"""
from __future__ import annotations

import queue
import threading
from concurrent.futures import Future
from typing import Any, Callable

from society.conductor import Conductor


class SimLoop:
    def __init__(self, conductor: Conductor) -> None:
        self.c = conductor
        self._lock = threading.Lock()
        self._running = False       # 自动连跑
        self._step_budget = 0       # 待执行的手动步数(幂等:最多 1)
        self._busy = False          # 正在跑某一拍 —— 用于 step 幂等去重
        self._stop = False          # 关闭信号
        self._wake = threading.Event()
        # 待执行的 world 写操作(注入等),由后台线程在拍间 drain。
        self._pending: queue.Queue[tuple[Callable[[], Any], Future]] = queue.Queue()
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

    def step(self) -> None:
        """请求步进一拍。【幂等】:已有步进在途(正在跑或已排队)、或处于自动模式时,
        重复调用一律忽略 —— 连点「步进」也只走一拍,本拍跑完才接受下一次。"""
        with self._lock:
            if self._busy or self._step_budget > 0 or self._running:
                return
            self._step_budget = 1
        self._wake.set()

    def stop(self) -> None:
        """关闭后台线程(进程退出时调用)。"""
        self._stop = True
        self._wake.set()

    def stop_and_join(self, timeout: float = 10.0) -> None:
        """停后台线程并等它退出 —— 切场景时用。

        join 会阻塞到当前拍跑完(LLM 不可中断),故调用方应丢到线程池(asyncio.to_thread)
        执行,避免卡住事件循环。"""
        self.stop()
        self._thread.join(timeout=timeout)

    def submit(self, fn: Callable[[], Any]) -> Future:
        """把一个 world 写操作排给后台线程,在拍间执行。返回 Future 供调用方等结果。

        所有改 world 的动作都该走这里 —— 保证写入单线程化,与推进 / 落盘不打架。"""
        fut: Future = Future()
        self._pending.put((fn, fut))
        self._wake.set()
        return fut

    def status(self) -> dict:
        """当前运行态快照,供 REST 查询。"""
        with self._lock:
            return {
                "running": self._running,
                "step_budget": self._step_budget,
                "busy": self._busy,
                "tick": self.c.world.tick,
                "terminal": self.c.is_terminal(),
            }

    # —— 后台线程主体 ——

    def _drain(self) -> None:
        """执行所有排队的 world 写操作。只在后台线程调用。"""
        while True:
            try:
                fn, fut = self._pending.get_nowait()
            except queue.Empty:
                return
            try:
                fut.set_result(fn())
            except Exception as exc:  # 把异常透回提交方,不掀翻循环
                fut.set_exception(exc)

    def _loop(self) -> None:
        while not self._stop:
            # 先清掉待办写操作(注入等):保证所有 world 写入都在本线程、且先于本拍推进。
            self._drain()

            with self._lock:
                go = self._running or self._step_budget > 0
            if not go:
                self._wake.wait(timeout=1.0)   # 空闲挂起,被 run / step / submit 唤醒
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
            # _busy 期间到来的 step 请求被幂等忽略,连点不堆积。
            with self._lock:
                self._busy = True
            self.c.step(1)
            with self._lock:
                self._busy = False
                if self._step_budget > 0:
                    self._step_budget -= 1
