from __future__ import annotations
from society.config import load_config
from society.engine.turn_engine import run_turn
from society.persistence import load_world, save_world
from content.scenarios.triangle import build_triangle_world
from content.scenarios.graduation_trip import build_graduation_trip_world
from content.scenarios.test import build_test_world

def main() -> None:
    world = load_world() or build_test_world()
    for _ in range(load_config().simulation.num_turns):
        run_turn(world)
        save_world(world)


if __name__ == "__main__":
    main()
