"""WebSocketSink + 连接广播桥接 —— 引擎 → 浏览器 的实时数据管道。

## 线程模型(这层全部复杂度的来源)

引擎是同步阻塞的:`run_turn` 顺序等每个 agent 的 LLM 往返,因此模拟循环只能跑在
一个【后台线程】里。而 websocket 活在 asyncio 的【事件循环线程】。两个线程之间要
传消息,且 asyncio.Queue 不是线程安全的。

解法:让 history / connections / 各连接的 queue 这些内部状态【只】在事件循环线程
被触碰。emit() 在模拟线程里跨线程做的唯一一件事,是 `loop.call_soon_threadsafe`
(该 API 本身线程安全)——把"投递"调度回事件循环执行。于是内部状态全程单线程访问,
一把锁都不用,竞态从根上消失。

ConnectionManager 管"连接 / 广播 / 历史回放";WebSocketSink 是薄薄的 SimSink
适配器,把引擎吐出的 Signal 序列化后交给 manager。
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from society.stream.signals import Signal
from ui.web.serializers import signal_to_dict

if TYPE_CHECKING:
    from starlette.websockets import WebSocket


class ConnectionManager:
    """持有所有活动 websocket,负责历史回放 + 实时广播。

    全部内部状态(_history / _queues)只在事件循环线程被读写 —— 跨线程入口
    publish() 只经 call_soon_threadsafe 调度,绝不直接动这些结构。
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        # 每个连接一条独立队列;广播 = 往每条队列各 put 一份。
        self._queues: set[asyncio.Queue[dict]] = set()
        # 发出过的所有消息,供新连接接入时完整回放(单人观察,刻意不设上限,
        # 让后连上的观察者也能看到整段剧情)。
        self._history: list[dict] = []

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """由 server 在 startup 时注入正在运行的事件循环。
        必须在模拟线程启动【之前】调用,保证 publish 一定有 loop 可用。"""
        self._loop = loop

    # —— 跨线程入口(模拟线程调用) ——

    def publish(self, message: dict) -> None:
        """把一条已序列化的消息投递出去。从【模拟线程】调用。

        只经 call_soon_threadsafe 把真正的投递动作(_deliver)调度回事件循环线程,
        自身不触碰任何内部状态。loop 尚未绑定时静默丢弃(正常流程不会发生)。"""
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._deliver, message)

    def _deliver(self, message: dict) -> None:
        """在事件循环线程执行:记入历史 + 分发给每条连接队列。"""
        self._history.append(message)
        for q in self._queues:
            q.put_nowait(message)

    # —— 连接生命周期(事件循环线程调用) ——

    def connect(self) -> asyncio.Queue[dict]:
        """新连接登记:建一条队列,先灌入完整历史回放,再加入广播名单。

        这两步在事件循环单线程里原子完成 —— 此后到达的 publish 必然进该队列,
        既不会漏掉回放与注册之间的消息,也不会重复。返回的队列由调用方泵给 websocket。"""
        q: asyncio.Queue[dict] = asyncio.Queue()
        for message in self._history:
            q.put_nowait(message)
        self._queues.add(q)
        return q

    def disconnect(self, q: asyncio.Queue[dict]) -> None:
        self._queues.discard(q)


class WebSocketSink:
    """SimSink 实现:把引擎吐出的 Signal 序列化后交给 ConnectionManager 广播。

    god 视角不在这里过滤 —— PUBLIC / PRIVATE 都推下去,可见性带在每条 event 上,
    由前端做"内心图层"的叠加。这正是 web 相对 CLISink 的升级:观察视角从后端的
    全局开关,变成前端可随时切换的渲染图层。
    """

    def __init__(self, manager: ConnectionManager) -> None:
        self.manager = manager

    def emit(self, signal: Signal) -> None:
        self.manager.publish(signal_to_dict(signal))
