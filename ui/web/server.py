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

from society.conductor import Conductor
from society.engine.director import Director
from society.persistence import load_world
from content.loader import load_scenario
from ui.web.serializers import agent_brief, agent_dossier, location_to_dict
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


# —— 静态页:必须最后挂载(前缀 "/" 会吞掉所有路径) ——

app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
