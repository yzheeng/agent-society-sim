"""Console:命令行交互壳。纯适配器——解析一行输入 → 调一个 Conductor 方法。

所有控制语义住在 Conductor;这里只做按键到方法的翻译 + 几个交互式录入。
模式(手动 / 自动)只决定「回车」做什么:手动走一拍,自动跑到终局。
"""
from __future__ import annotations

from society.conductor import Conductor

_HELP = """\
命令:
  回车 / n [k]   推进(手动:1 拍;自动模式下空回车=跑到终局)。n 3 = 走 3 拍
  auto [k]       自动模式:跑到终局(或指定 k 拍),Ctrl-C 打断
  manual         切回手动模式
  g              上帝视角开关(心声 / 盘算 显隐)
  i              注入·客观事实(旁白:选地点+内容,下一拍当众发生)
  w              注入·冲动(往某角色塞一瞬念头,只拨动 TA 下一步,用完即清)
  b              注入·信念(往某角色植入持久认知,长留自我、染色其后续)
  who [id]       查看角色私密档案;who 不带 id 列出所有角色
  h              帮助
  q              退出(已自动存档)
"""


class Console:
    def __init__(self, conductor: Conductor) -> None:
        self.c = conductor
        self.mode = "manual"  # manual | auto

    def run(self) -> None:
        print(_HELP)
        self._status()
        while True:
            try:
                line = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not self._handle(line):
                break
        print("已退出(存档已落盘)。")

    # —— 命令分发 ——

    def _handle(self, line: str) -> bool:
        """返回 False 表示退出。"""
        parts = line.split()
        cmd = parts[0].lower() if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "q":
            return False
        if cmd in ("h", "help", "?"):
            print(_HELP)
        elif cmd == "":
            self._advance_default()
        elif cmd == "n":
            self.c.step(self._as_int(arg, 1))
        elif cmd == "auto":
            self.mode = "auto"
            self._run_auto(self._as_int(arg, 0))
        elif cmd == "manual":
            self.mode = "manual"
            print("[手动模式]")
        elif cmd == "g":
            self.c.set_god(not self.c.god())
            print(f"[上帝视角:{'开' if self.c.god() else '关'}]")
        elif cmd == "i":
            self._inject_fact()
        elif cmd == "w":
            self._inject_impulse()
        elif cmd == "b":
            self._inject_belief()
        elif cmd == "who":
            self._who(arg)
        else:
            print(f"未知命令:{cmd}(h 看帮助)")

        if self.c.is_terminal():
            print("\n[剧情已到终局,q 退出]")
        return True

    def _advance_default(self) -> None:
        if self.mode == "auto":
            self._run_auto(0)
        else:
            self.c.step(1)

    def _run_auto(self, k: int) -> None:
        try:
            if k > 0:
                self.c.step(k)
            else:
                self.c.run_to_terminal()
        except KeyboardInterrupt:
            print("\n[自动模式被打断,回到提示符]")

    # —— 交互式录入 ——

    def _inject_fact(self) -> None:
        print("可选地点:")
        for loc in self.c.locations():
            print(f"  {loc.id} —— {loc.name}")
        loc_id = input("地点 id> ").strip()
        if loc_id not in {l.id for l in self.c.locations()}:
            print("地点不存在,已取消。")
            return
        content = input("发生了什么(旁白)> ").strip()
        if not content:
            print("内容为空,已取消。")
            return
        self.c.inject_fact(loc_id, content)
        print("[客观事实已排,下一拍在此地点当众发生]")

    def _inject_impulse(self) -> None:
        sel = self._pick_agent("塞进 TA 心里的一瞬念头> ")
        if sel is None:
            return
        agent_id, content = sel
        self.c.inject_impulse(agent_id, content)
        print(f"[已给 {self.c.dossier(agent_id).name} 一阵冲动,只影响 TA 下一步]")

    def _inject_belief(self) -> None:
        sel = self._pick_agent("植入 TA 心里的持久认知> ")
        if sel is None:
            return
        agent_id, content = sel
        self.c.inject_belief(agent_id, content)
        print(f"[已为 {self.c.dossier(agent_id).name} 植入信念,将长留并染色其后续]")

    def _pick_agent(self, content_prompt: str) -> tuple[str, str] | None:
        """选角色 + 录内容,供冲动 / 信念共用。取消返回 None。"""
        print("可选角色:")
        for a in self.c.agents():
            print(f"  {a.id} —— {a.name}")
        agent_id = input("角色 id> ").strip()
        if agent_id not in {a.id for a in self.c.agents()}:
            print("角色不存在,已取消。")
            return None
        content = input(content_prompt).strip()
        if not content:
            print("内容为空,已取消。")
            return None
        return agent_id, content

    # —— 查询 ——

    def _who(self, arg: str) -> None:
        if not arg:
            for a in self.c.agents():
                print(f"  {a.id} —— {a.name}|{a.public_persona[:30]}…")
            return
        try:
            a = self.c.dossier(arg)
        except KeyError:
            print(f"没有角色 {arg}。")
            return
        print(f"\n【{a.name}({a.id})】@ {a.location_id}")
        print(f"  人前      :{a.public_persona}")
        print(f"  真实欲求  :{a.private_goal}")
        print(f"  秘密      :{a.secret}")
        print(f"  当前盘算  :{a.plan or '(无)'}")
        if a.beliefs:
            print("  信念(植入):")
            for b in a.beliefs:
                print(f"    - {b}")
        if a.impulses:
            print(f"  待发冲动  :{a.impulses}")
        print(f"  关系      :{a.relationships}")
        if a.memory:
            print("  近期记忆  :")
            for m in a.memory[-5:]:
                print(f"    - {m}")

    # —— 杂 ——

    def _status(self) -> None:
        print(f"[模式:{'自动' if self.mode == 'auto' else '手动'} | "
              f"上帝视角:{'开' if self.c.god() else '关'} | tick {self.c.world.tick}]")

    @staticmethod
    def _as_int(s: str, default: int) -> int:
        try:
            return int(s)
        except (ValueError, TypeError):
            return default
