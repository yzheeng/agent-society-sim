from __future__ import annotations
from society.conductor import Conductor
from society.engine.director import Director
from society.persistence import load_world
from ui.cli import CLISink
from ui.console import Console
from content.loader import load_scenario

# 要跑哪个场景:对应 content/scenarios/<SCENARIO>.yaml
SCENARIO = "test"

def main() -> None:
    # scenario 是 calendar 的 source of truth(不持久化),先建出来:
    # - 无存档:直接用它作为初始 world
    # - 有存档:用存档恢复 tick / agents / event_log,calendar 从 scenario 重新挂上
    scenario_world = load_scenario(SCENARIO)
    world = load_world() or scenario_world
    if world.calendar is None:
        world.calendar = scenario_world.calendar
    # 火种不再写死在 scenario,全部由命令行(Console 的 i / w)临场注入。
    director = Director([])

    conductor = Conductor(world, director, CLISink(god=False))
    Console(conductor).run()


if __name__ == "__main__":
    main()
