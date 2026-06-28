"""FastAPI 观察台后端 —— 把模拟以 web 服务形态托管在后台。

形状:
- 进程常驻持有一个可替换的 Runtime(world / Conductor / SimLoop),模拟跑在后台线程。
- websocket /ws  :实时推 Signal(新连接先收完整历史回放;切场景推 reset 让前端清屏)。
- REST  /api/*   :控制(run/pause/step)、注入、查询、历史档案、场景切换。
- 静态页 /       :原生单页观察台(挂载在最后,前缀会吞路径,必须晚于其它路由注册)。

场景切换:存档按场景隔离到 data/<scenario>/。Runtime.reset_to 停旧 sim → 切存档 →
重建世界 → 广播 reset → 起新 sim。当前活动场景记在 data/active_scenario,跨重启恢复。

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

from society.config import load_config
from society.conductor import Conductor
from society.engine.director import Director
from society.persistence import load_world, use_scenario
from content.loader import list_scenarios, load_scenario
from ui.web.serializers import agent_brief, agent_dossier, event_entry, location_to_dict
from ui.web.sim_loop import SimLoop
from ui.web.ws_sink import ConnectionManager, WebSocketSink

# 无存档、也没记过活动场景时的兜底默认场景。
DEFAULT_SCENARIO = "test"

_STATIC_DIR = Path(__file__).parent / "static"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _active_file() -> Path:
    """记录"当前活动场景"的文件,放 data/ 根(不属于任何单个场景子目录)。"""
    return _PROJECT_ROOT / load_config().persistence.data_dir / "active_scenario"


def _read_active() -> str:
    f = _active_file()
    if f.exists():
        name = f.read_text(encoding="utf-8").strip()
        if name in list_scenarios():
            return name
    return DEFAULT_SCENARIO


def _write_active(name: str) -> None:
    f = _active_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(name, encoding="utf-8")


class Runtime:
    """可替换的"当前世界"容器:持有 manager(跨场景常驻) + conductor + sim(随场景重建)。

    所有端点都经 _rt 取最新的 conductor/sim —— 切场景后它们换了新对象,端点自然跟到新世界。
    """

    def __init__(self) -> None:
        self.manager = ConnectionManager()   # 跨场景常驻:websocket 连接不因切场景而断
        self.scenario = _read_active()
        self._activate(self.scenario)

    def _activate(self, scenario: str) -> None:
        """按场景装配 world/conductor/sim —— 与 run.py 同一套逻辑,存档隔离到该场景目录。"""
        use_scenario(scenario)
        scen_world = load_scenario(scenario)
        world = load_world() or scen_world
        if world.calendar is None:
            world.calendar = scen_world.calendar
        self.conductor = Conductor(world, Director([]), WebSocketSink(self.manager))
        self.sim = SimLoop(self.conductor)
        self.scenario = scenario

    def start(self) -> None:
        self.sim.start()

    def stop(self) -> None:
        self.sim.stop()

    async def reset_to(self, scenario: str) -> None:
        """切到另一个场景:停旧线程(丢线程池避免卡事件循环)→ 清屏广播 → 重建 → 起新线程。"""
        self.sim.pause()
        await asyncio.to_thread(self.sim.stop_and_join)
        self.manager.reset()        # 事件循环线程:清历史 + 给前端推 reset
        _write_active(scenario)
        self._activate(scenario)
        self.sim.start()


_rt = Runtime()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # 在事件循环就绪后绑定它,再启动模拟线程 —— 保证 publish 一定有 loop 可用。
    _rt.manager.bind_loop(asyncio.get_running_loop())
    _rt.start()
    yield
    _rt.stop()


app = FastAPI(title="社会模拟观察台", lifespan=_lifespan)


# —— websocket:实时信号流 ——

@app.websocket("/ws")
async def ws_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = _rt.manager.connect()  # 原子地:灌入历史回放 + 加入广播名单
    try:
        while True:
            message = await queue.get()
            await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        _rt.manager.disconnect(queue)


# —— REST 控制面(翻标志位,瞬时返回) ——

@app.post("/api/run")
async def api_run() -> JSONResponse:
    _rt.sim.run()
    return JSONResponse(_rt.sim.status())


@app.post("/api/pause")
async def api_pause() -> JSONResponse:
    _rt.sim.pause()
    return JSONResponse(_rt.sim.status())


@app.post("/api/step")
async def api_step() -> JSONResponse:
    _rt.sim.step()
    return JSONResponse(_rt.sim.status())


# —— REST 查询(直接读 domain,经序列化层) ——

@app.get("/api/state")
async def api_state() -> JSONResponse:
    cal = _rt.conductor.world.calendar
    return JSONResponse({
        **_rt.sim.status(),
        "scenario": _rt.scenario,
        "terminal_event": cal.terminal_event if cal is not None else None,
    })


@app.get("/api/locations")
async def api_locations() -> JSONResponse:
    return JSONResponse([location_to_dict(l) for l in _rt.conductor.locations()])


@app.get("/api/agents")
async def api_agents() -> JSONResponse:
    return JSONResponse([agent_brief(a) for a in _rt.conductor.agents()])


@app.get("/api/agents/full")
async def api_agents_full() -> JSONResponse:
    """一次返回所有角色全字段(含私密层),供「角色」总览卡片,免前端 N 次请求。"""
    return JSONResponse([agent_dossier(a) for a in _rt.conductor.agents()])


@app.get("/api/agent/{agent_id}")
async def api_agent(agent_id: str) -> JSONResponse:
    try:
        agent = _rt.conductor.dossier(agent_id)
    except KeyError:
        return JSONResponse({"error": f"没有角色 {agent_id}"}, status_code=404)
    return JSONResponse(agent_dossier(agent))


# —— 场景:列出 / 切换(导入初始化) ——

class _ScenarioIn(BaseModel):
    name: str


@app.get("/api/scenario/list")
async def api_scenario_list() -> JSONResponse:
    return JSONResponse({"scenarios": list_scenarios(), "current": _rt.scenario})


@app.post("/api/scenario/load")
async def api_scenario_load(payload: _ScenarioIn) -> JSONResponse:
    if payload.name not in list_scenarios():
        return JSONResponse({"error": f"场景不存在:{payload.name}"}, status_code=400)
    await _rt.reset_to(payload.name)
    return JSONResponse({"ok": True, "scenario": payload.name})


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
    fut = _rt.sim.submit(fn)
    try:
        await asyncio.wait_for(asyncio.wrap_future(fut), timeout=_INJECT_TIMEOUT)
        return True
    except asyncio.TimeoutError:
        return False


@app.post("/api/inject/fact")
async def api_inject_fact(payload: _FactIn) -> JSONResponse:
    content = payload.content.strip()
    if payload.location_id not in _rt.conductor.world.locations:
        return JSONResponse({"error": "地点不存在"}, status_code=400)
    if not content:
        return JSONResponse({"error": "内容为空"}, status_code=400)
    done = await _submit_and_wait(lambda: _rt.conductor.inject_fact(payload.location_id, content))
    return JSONResponse({"ok": True, "applied": done})


@app.post("/api/inject/impulse")
async def api_inject_impulse(payload: _AgentMsgIn) -> JSONResponse:
    content = payload.content.strip()
    if payload.agent_id not in _rt.conductor.world.agents:
        return JSONResponse({"error": "角色不存在"}, status_code=400)
    if not content:
        return JSONResponse({"error": "内容为空"}, status_code=400)
    done = await _submit_and_wait(lambda: _rt.conductor.inject_impulse(payload.agent_id, content))
    return JSONResponse({"ok": True, "applied": done})


@app.post("/api/inject/belief")
async def api_inject_belief(payload: _AgentMsgIn) -> JSONResponse:
    content = payload.content.strip()
    if payload.agent_id not in _rt.conductor.world.agents:
        return JSONResponse({"error": "角色不存在"}, status_code=400)
    if not content:
        return JSONResponse({"error": "内容为空"}, status_code=400)
    done = await _submit_and_wait(lambda: _rt.conductor.inject_belief(payload.agent_id, content))
    return JSONResponse({"ok": True, "applied": done})


# —— 历史档案:浏览整段 event_log(= data/<scenario>/events.jsonl 的全量历史) ——

@app.get("/api/log/events")
async def api_log_events(
    actor: str | None = None,
    type: str | None = None,
    visibility: str | None = None,
    limit: int = 2000,
) -> JSONResponse:
    # 先快照一份引用,避免迭代时后台线程 append 造成不一致。
    world = _rt.conductor.world
    events = list(world.event_log)
    items = [event_entry(world, e) for e in events]
    if actor:
        items = [x for x in items if x["actor_id"] == actor]
    if type:
        items = [x for x in items if x["type"] == type]
    if visibility:
        items = [x for x in items if x["visibility"] == visibility]
    return JSONResponse({"total": len(items), "events": items[-limit:]})


# —— 静态页:必须最后挂载(前缀 "/" 会吞掉所有路径) ——

app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
