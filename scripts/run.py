from __future__ import annotations
from society.config import load_config
from society.engine.turn_engine import run_turn
from content.scenarios.triangle import build_triangle_world


def main() -> None:
    world = build_triangle_world()
    for _ in range(load_config().simulation.num_turns):
        run_turn(world)


if __name__ == "__main__":
    main()
