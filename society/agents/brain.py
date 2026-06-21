"""
agent 行动层:把 perception 喂给 LLM,拿回 tool_calls,翻译成 Event。
"""
from __future__ import annotations

import json

from society.core.models import Event
from society.core.enums import ActionType, Visibility
from society.core.perception import Perception
from society.llm.client import chat
from society.agents.prompts import SYSTEM_PROMPT, build_user_prompt
from society.agents.tools import build_tools
from society.agents.memory import recall


def _normalize(s: str) -> str:
    """把 LLM 给的 content 单行化:所有连续 whitespace(含 \\n / \\t / 多个空格)折成一个空格。

    memory 单条 = 单行是 prompts.py:53 (`- {m}`) 渲染逻辑的隐式契约;
    event_log content 单行也便于 jsonl 阅读。在这里统一兜底,renderer 一行不动。
    """
    return " ".join(s.split())


def decide(perception: Perception, tick: int) -> list[Event]:
    me = perception.self_agent
    recalled = recall(me)
    # 导演私语塞进来的冲动:读出来交给 prompt 醒目呈现,消费即清(只影响这一次行动)。
    impulses = list(me.impulses)
    me.impulses.clear()
    user_prompt = build_user_prompt(perception, recalled, impulses)
    tools = build_tools(perception)

    msg = chat(user_prompt, system=SYSTEM_PROMPT, tools=tools)

    # 兜底:tool_choice=required 理应保证总有 tool_calls,但 DeepSeek 偶发不遵守。
    # 留个内观痕迹便于事后排查,不让这一拍空过。
    if not msg.tool_calls:
        return [Event(
            tick=tick,
            actor_id=me.id,
            type=ActionType.THINK,
            content=f"(LLM 未调 tool)原文:{_normalize(msg.content or '')}",
            location_id=me.location_id,
            visibility=Visibility.PRIVATE,
        )]

    events: list[Event] = []
    for call in msg.tool_calls:
        name = call.function.name
        try:
            args = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            continue
        try:
            action_type = ActionType(name)
        except ValueError:
            continue

        if action_type == ActionType.MOVE:
            destination = args.get("destination")
            if not destination:
                continue
            events.append(Event(
                tick=tick,
                actor_id=me.id,
                type=ActionType.MOVE,
                content="",  # apply_event 用模板渲染
                location_id=me.location_id,
                destination_id=destination,
                visibility=Visibility.PUBLIC,
            ))
        else:
            content = _normalize(str(args.get("content", "")))
            if not content:
                continue
            visibility = (
                Visibility.PRIVATE
                if action_type in (ActionType.THINK, ActionType.PLAN)
                else Visibility.PUBLIC
            )
            events.append(Event(
                tick=tick,
                actor_id=me.id,
                type=action_type,
                content=content,
                location_id=me.location_id,
                visibility=visibility,
            ))

    # MOVE 独占一拍:含 MOVE 时只保留首条 MOVE + 所有 THINK / PLAN,
    # 丢弃 SPEAK / ACT 和多余的 MOVE。脚一旦迈出去就专心走。
    if any(e.type == ActionType.MOVE for e in events):
        filtered: list[Event] = []
        move_kept = False
        for e in events:
            if e.type == ActionType.MOVE:
                if not move_kept:
                    filtered.append(e)
                    move_kept = True
            elif e.type in (ActionType.THINK, ActionType.PLAN):
                filtered.append(e)
            # SPEAK / ACT:丢弃
        events = filtered

    return events
