from __future__ import annotations
from society.config import load_config
from society.engine.turn_engine import run_turn
from society.persistence import load_world, save_world
from ui.cli import CLISink
from content.scenarios.test import build_test_world

def main() -> None:
    # scenario 是 calendar 的 source of truth(不持久化),先建出来:
    # - 无存档:直接用它作为初始 world
    # - 有存档:用存档恢复 tick / agents / event_log,calendar 从 scenario 重新挂上
    scenario_world = build_test_world()
    world = load_world() or scenario_world
    if world.calendar is None:
        world.calendar = scenario_world.calendar
    sink = CLISink()
    for _ in range(load_config().simulation.num_turns):
        run_turn(world, sink)
        save_world(world)


if __name__ == "__main__":
    main()
