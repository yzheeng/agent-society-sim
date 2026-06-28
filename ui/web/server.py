"""FastAPI 观察台后端 —— 把模拟以 web 服务形态托管在后台。

形状:
- 进程常驻持有 world / Conductor,模拟跑在 SimLoop 的后台线程里。
- websocket /ws  :实时推 Signal(新连接先收完整历史回放)。
- REST  /api/*   :控制(run/pause/step)只翻标志位、瞬时返回;查询直接读 domain。
- 静态页 /       :原生单页观察台(挂载在最后,前缀会吞路径,必须晚于其它路由注册)。

与 run.py(CLI 入口)对称:那边用 CLISink + Console,这边用 WebSocketSink + 浏览器。
引擎 / Conductor 一行不动。
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from society.conductor import Conductor
from society.engine.director import Director
from society.persistence import load_world
from content.loader import load_scenario
from ui.web.serializers import agent_brief, agent_dossier, event_entry, location_to_dict
from ui.web.sim_loop import SimLoop
from ui.web.ws_sink import ConnectionManager, WebSocketSink

# 要跑哪个场景:对应 content/scenarios/<SCENARIO>.yaml
SCENARIO = "test"

_STATIC_DIR = Path(__file__).parent / "static"


def _build_conductor(manager: ConnectionManager) -> Conductor:
    """构造 world / director / conductor —— 与 run.py 同一套装配逻辑,
    只把 sink 从 CLISink 换成 WebSocketSink。"""
    scenario_world = load_scenario(SCENARIO)
    world = load_world() or scenario_world
    if world.calendar is None:
        world.calendar = scenario_world.calendar
    director = Director([])
    return Conductor(world, director, WebSocketSink(manager))


_manager = ConnectionManager()
_conductor = _build_conductor(_manager)
_sim = SimLoop(_conductor)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # 在事件循环就绪后绑定它,再启动模拟线程 —— 保证 publish 一定有 loop 可用。
    _manager.bind_loop(asyncio.get_running_loop())
    _sim.start()
    yield
    _sim.stop()


app = FastAPI(title="社会模拟观察台", lifespan=_lifespan)


# —— websocket:实时信号流 ——

@app.websocket("/ws")
async def ws_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = _manager.connect()  # 原子地:灌入历史回放 + 加入广播名单
    try:
        while True:
            message = await queue.get()
            await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        _manager.disconnect(queue)


# —— REST 控制面(翻标志位,瞬时返回) ——

@app.post("/api/run")
async def api_run() -> JSONResponse:
    _sim.run()
    return JSONResponse(_sim.status())


@app.post("/api/pause")
async def api_pause() -> JSONResponse:
    _sim.pause()
    return JSONResponse(_sim.status())


@app.post("/api/step")
async def api_step(k: int = 1) -> JSONResponse:
    _sim.step(k)
    return JSONResponse(_sim.status())


# —— REST 查询(直接读 domain,经序列化层) ——

@app.get("/api/state")
async def api_state() -> JSONResponse:
    cal = _conductor.world.calendar
    return JSONResponse({
        **_sim.status(),
        "scenario": SCENARIO,
        "terminal_event": cal.terminal_event if cal is not None else None,
    })


@app.get("/api/locations")
async def api_locations() -> JSONResponse:
    return JSONResponse([location_to_dict(l) for l in _conductor.locations()])


@app.get("/api/agents")
async def api_agents() -> JSONResponse:
    return JSONResponse([agent_brief(a) for a in _conductor.agents()])


@app.get("/api/agent/{agent_id}")
async def api_agent(agent_id: str) -> JSONResponse:
    try:
        agent = _conductor.dossier(agent_id)
    except KeyError:
        return JSONResponse({"error": f"没有角色 {agent_id}"}, status_code=404)
    return JSONResponse(agent_dossier(agent))


# —— 注入(三个维度):经 sim.submit 排给后台线程,保证 world 写入单线程化 ——

class _FactIn(BaseModel):
    location_id: str
    content: str


class _AgentMsgIn(BaseModel):
    agent_id: str
    content: str


# 注入排在拍间执行:若正赶上某拍在跑(LLM 阻塞),最长等它跑完。超时不算失败,
# 操作仍会在下一次拍间隙被 drain 执行,只是这次请求先返回"已排队"。
_INJECT_TIMEOUT = 120


async def _submit_and_wait(fn) -> bool:
    """把写操作排给模拟线程并等它落定。返回是否在超时内完成。"""
    fut = _sim.submit(fn)
    try:
        await asyncio.wait_for(asyncio.wrap_future(fut), timeout=_INJECT_TIMEOUT)
        return True
    except asyncio.TimeoutError:
        return False


@app.post("/api/inject/fact")
async def api_inject_fact(payload: _FactIn) -> JSONResponse:
    content = payload.content.strip()
    if payload.location_id not in _conductor.world.locations:
        return JSONResponse({"error": "地点不存在"}, status_code=400)
    if not content:
        return JSONResponse({"error": "内容为空"}, status_code=400)
    done = await _submit_and_wait(lambda: _conductor.inject_fact(payload.location_id, content))
    return JSONResponse({"ok": True, "applied": done})


@app.post("/api/inject/impulse")
async def api_inject_impulse(payload: _AgentMsgIn) -> JSONResponse:
    content = payload.content.strip()
    if payload.agent_id not in _conductor.world.agents:
        return JSONResponse({"error": "角色不存在"}, status_code=400)
    if not content:
        return JSONResponse({"error": "内容为空"}, status_code=400)
    done = await _submit_and_wait(lambda: _conductor.inject_impulse(payload.agent_id, content))
    return JSONResponse({"ok": True, "applied": done})


@app.post("/api/inject/belief")
async def api_inject_belief(payload: _AgentMsgIn) -> JSONResponse:
    content = payload.content.strip()
    if payload.agent_id not in _conductor.world.agents:
        return JSONResponse({"error": "角色不存在"}, status_code=400)
    if not content:
        return JSONResponse({"error": "内容为空"}, status_code=400)
    done = await _submit_and_wait(lambda: _conductor.inject_belief(payload.agent_id, content))
    return JSONResponse({"ok": True, "applied": done})


# —— 历史档案:浏览整段 event_log(= data/events.jsonl 的全量历史) ——

@app.get("/api/log/events")
async def api_log_events(
    actor: str | None = None,
    type: str | None = None,
    visibility: str | None = None,
    limit: int = 2000,
) -> JSONResponse:
    # 先快照一份引用,避免迭代时后台线程 append 造成不一致。
    events = list(_conductor.world.event_log)
    items = [event_entry(_conductor.world, e) for e in events]
    if actor:
        items = [x for x in items if x["actor_id"] == actor]
    if type:
        items = [x for x in items if x["type"] == type]
    if visibility:
        items = [x for x in items if x["visibility"] == visibility]
    return JSONResponse({"total": len(items), "events": items[-limit:]})


# —— 静态页:必须最后挂载(前缀 "/" 会吞掉所有路径) ——

app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
