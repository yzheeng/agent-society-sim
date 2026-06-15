from __future__ import annotations

from content.scenarios.campus import build_campus_world
from society.engine.turn_engine import run_turn


def main() -> None:
    world = build_campus_world()
    for _ in range(2):
        run_turn(world)


if __name__ == "__main__":
    main()