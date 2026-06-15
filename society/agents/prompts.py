"""
把一个 agent 的感知,拼成喂给 LLM 的 prompt。
"""
from __future__ import annotations

from society.engine.perception import Perception
import json
from society.core.enums import ActionType, Visibility

SYSTEM_PROMPT = (
    "你在参与一场多人社会模拟。你将扮演一个角色,"
    "依据你的人设、私密目标和当前处境,做出一个符合性格的反应。"
    "记住:你的私密目标和秘密只有你自己知道,别人看不到你的内心。"
    "不要解释、不要旁白,只直接给出你这个角色此刻的反应。"
)


def build_user_prompt(perception: Perception, recalled: list[str]) -> str:
    """把感知拼成一段"此刻的处境描述",末尾要求它给出一个动作。"""
    me = perception.self_agent

    # —— 1. 我是谁——
    lines = [
        f"你是{me.name}。",
        f"【公开人设】{me.public_persona}",
        f"【你的私密目标】{me.private_goal}",
        f"【你的秘密】{me.secret}",
    ]
    if me.plan:
        lines.append(f"【你眼下的打算】{me.plan}")

    # —— 2. 现场还有谁  ——
    if perception.others_present:
        lines.append("\n【此刻在场的其他人(你只了解他们公开的一面)】")
        for other in perception.others_present:
            lines.append(f"- {other.name}:{other.public_persona}")
    else:
        lines.append("\n【现场只有你一个人】")

    # —— 3. 最近经历(短期记忆) ——
    if recalled:
        lines.append("\n【你最近经历的(只有你自己记得,包括你没说出口的心声)】")
        lines.extend(f"- {m}" for m in recalled)

    # —— 4. 我此刻看见/听到了什么——
    if perception.visible_events:
        lines.append("\n【你此刻看到/听到的】")
        for e in perception.visible_events:
            lines.append(f"- {e.actor_id}:{e.content}")
    else:
        lines.append("\n【此刻周围很安静,没有新的动静】")

    # —— 4. 要它干什么:只用 JSON 回应,动作种类 + 内容 ——
    lines.append(
        "\n现在请只用 JSON 回应,不要任何解释、旁白或代码围栏。\n"
        "你可以在这一回合同时做不止一件事:既说出口的话,也藏在心里的念头。\n"
        "每做一件事,就输出一个 JSON 对象,各占一行,格式严格如下:\n"
        '{"action": "speak", "content": "你当众说出口的话"}\n'
        '{"action": "think", "content": "只有你自己知道的心声"}\n'
        "speak = 当众说出口;think = 只有你自己知道的心声。\n"
        "如果这一刻你只想做一件事,就只输出一个对象;不要输出 JSON 数组,逐行give出对象即可。"
    )

    return "\n".join(lines)


# 动作种类 → (ActionType, Visibility)。
_ACTION_MAP = {
    "speak": (ActionType.SPEAK, Visibility.PUBLIC),
    "think": (ActionType.THINK, Visibility.PRIVATE),
}


def parse_response(raw: str) -> list[tuple[ActionType, Visibility, str]]:
    """
    解析 LLM response,可能含【多个】动作对象(各占一行的裸对象)。
    返回一个列表;整体一个都没解析出来时,兜底成【一条】 PRIVATE 心声(用 list 包着)。
    """
    results: list[tuple[ActionType, Visibility, str]] = []
    decoder = json.JSONDecoder()

    idx = raw.find("{")
    while idx != -1:
        try:
            data, end = decoder.raw_decode(raw, idx)
        except json.JSONDecodeError:
            idx = raw.find("{", idx + 1)
            continue
        try:
            action = str(data["action"]).strip().lower()
            content = str(data["content"]).strip()
            action_type, visibility = _ACTION_MAP[action]
            if content:
                results.append((action_type, visibility, content))
        except (KeyError, ValueError):
            pass

        idx = raw.find("{", end)
    if not results:
        results.append(
            (ActionType.THINK, Visibility.PRIVATE, f"(解析失败)原文:{raw.strip()}")
        )
    return results


if __name__ == "__main__":
    cases = [
        '{"action": "speak", "content": "海报我来弄"}',
        '{"action":"think","content":"得想想"}\n{"action":"speak","content":"加油"}',
        '```json\n{"action":"think","content":"嗯"}\n```',
        '好的:{"action":"speak","content":"走"}',
        '我觉得我该说点什么',
    ]
    for c in cases:
        print(parse_response(c))
