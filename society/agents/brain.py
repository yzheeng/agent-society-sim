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


def _silence_event(me, tick: int) -> Event:
    """一条「当众没作声」的外显事件。无自由文本——渲染靠固定模板,content 只给
    上帝视角的 log / console 留个可读标记,角色侧(prompt / memory)不读它。"""
    return Event(
        tick=tick,
        actor_id=me.id,
        type=ActionType.SILENCE,
        content="(没作声)",
        location_id=me.location_id,
        visibility=Visibility.PUBLIC,
    )


# 外显层 = 这一拍能被旁人察觉的姿态;内心层 = 只有自己知道的念头。
_OUTWARD = (ActionType.SPEAK, ActionType.ACT, ActionType.MOVE, ActionType.SILENCE)
_INNER = (ActionType.THINK, ActionType.PLAN)


def _enforce_outward_stance(events: list[Event], me, tick: int) -> list[Event]:
    """每拍必须落一种外显姿态,内心戏(think/plan)只能附着、不能单独成拍。

    - 含 MOVE:脚迈出去就专心走——保留首条 MOVE + 所有内心戏,丢弃 speak/act/silence。
    - 否则有 speak/act:已经往外说/做了,沉默自相矛盾,丢弃多余的 silence。
    - 否则(只有内心戏,或 LLM 啥也没给):补一条沉默,把"心里转了一圈却被旁人
      当成没轮到"的黑洞填上——这正是本次改动要解决的问题。
    """
    if any(e.type == ActionType.MOVE for e in events):
        filtered: list[Event] = []
        move_kept = False
        for e in events:
            if e.type == ActionType.MOVE:
                if not move_kept:
                    filtered.append(e)
                    move_kept = True
            elif e.type in _INNER:
                filtered.append(e)
            # speak / act / silence / 多余的 move:丢弃
        return filtered

    if any(e.type in (ActionType.SPEAK, ActionType.ACT) for e in events):
        return [e for e in events if e.type != ActionType.SILENCE]

    # 只剩内心戏(或空):保留内心戏 + 一条规范化的沉默。
    inner = [e for e in events if e.type in _INNER]
    return inner + [_silence_event(me, tick)]


def decide(perception: Perception, tick: int) -> list[Event]:
    me = perception.self_agent
    recalled = recall(me)
    # 导演私语塞进来的冲动:读出来交给 prompt 醒目呈现,消费即清(只影响这一次行动)。
    impulses = list(me.impulses)
    me.impulses.clear()
    user_prompt = build_user_prompt(perception, recalled, impulses)
    tools = build_tools(perception)

    msg = chat(user_prompt, system=SYSTEM_PROMPT, tools=tools)

    events: list[Event] = []

    # 兜底:tool_choice=required 理应保证总有 tool_calls,但 DeepSeek 偶发不遵守。
    # 留个内观痕迹便于事后排查;外显层交给 _enforce_outward_stance 补一条沉默,
    # 这样这一拍在旁人眼里也不是凭空消失。
    if not msg.tool_calls:
        events.append(Event(
            tick=tick,
            actor_id=me.id,
            type=ActionType.THINK,
            content=f"(LLM 未调 tool)原文:{_normalize(msg.content or '')}",
            location_id=me.location_id,
            visibility=Visibility.PRIVATE,
        ))

    for call in msg.tool_calls or []:
        name = call.function.name
        try:
            args = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            continue
        try:
            action_type = ActionType(name)
        except ValueError:
            continue

        if action_type == ActionType.SILENCE:
            events.append(_silence_event(me, tick))
        elif action_type == ActionType.MOVE:
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

    return _enforce_outward_stance(events, me, tick)
