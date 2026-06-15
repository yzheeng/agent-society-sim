"""
把一个 agent 的感知,拼成喂给 LLM 的 prompt。
"""
from __future__ import annotations

from society.engine.perception import Perception
import json
from society.core.enums import ActionType, Visibility

SYSTEM_PROMPT = (
    "下面那段文字里的「我」就是你这个人——这个人的过往、心思、藏着的事、此刻的感官,都是你自己的,不是你在演谁。\n"
    "请以「我」的口吻,如实写下此刻的反应。不要解释,不要在第三方视角上点评自己,不要写「作为某某我...」这样的话。\n"
    "\n"
    "请只输出 JSON 对象,逐行裸对象,不带任何前后缀文字、不要数组、不要代码围栏。这一刻你可以输出以下几类,各占一行;按需输出 0 或多条,但 plan 至多 1 条:\n"
    '{"action":"speak","content":"我此刻当众说出口的话"}\n'
    '{"action":"think","content":"我此刻心里默默掠过的念头,谁也听不到"}\n'
    '{"action":"plan","content":"我此刻心里盘算的下一步——这只是我的眼前心思,等会儿会随情况再变"}\n'
)


def build_user_prompt(perception: Perception, recalled: list[str]) -> str:
    """把感知拼成一段角色的第一人称内独白,以「我」的口吻自然展开。"""
    me = perception.self_agent

    # —— 1. 我是谁(融成内独白,不打分层标签) ——
    lines = [
        f"我是{me.name}。",
        f"人前的我,{me.public_persona}。",
        f"可我心里真正想要的,是{me.private_goal}。",
        f"我藏着没让任何人知道的事:{me.secret}。",
    ]
    if me.plan:
        lines.append(f"我手头的打算:{me.plan}。")

    # —— 2. 此刻四周 ——
    if perception.others_present:
        lines.append("")
        lines.append("我抬眼环顾四周——")
        for other in perception.others_present:
            lines.append(f"{other.name}也在,在所有人眼里是「{other.public_persona}」。")
        lines.append("我跟他们打交道,看到的也就是他们摆给所有人看的那一面。")
    else:
        lines.append("")
        lines.append("此刻这儿就我一个,周围没别人。")

    # —— 3. 我脑子里还回响着的 ——
    if recalled:
        lines.append("")
        lines.append("我脑子里还回响着这些片段(只有我自己记得):")
        lines.extend(f"- {m}" for m in recalled)

    # —— 4. 此刻——只在确有他人发言时才铺;无事发生就不要硬塞"安静"
    #              ——以免让 LLM 误读成"大家在等我开口"的张力。
    if perception.visible_events:
        id_to_name = {other.id: other.name for other in perception.others_present}
        id_to_name[me.id] = me.name
        lines.append("")
        lines.append("就在此刻——")
        for e in perception.visible_events:
            speaker = id_to_name.get(e.actor_id, e.actor_id)
            lines.append(f"我听见{speaker}说:「{e.content}」")

    return "\n".join(lines)


# 动作种类 → (ActionType, Visibility)。
_ACTION_MAP = {
    "speak": (ActionType.SPEAK, Visibility.PUBLIC),
    "think": (ActionType.THINK, Visibility.PRIVATE),
    "plan":  (ActionType.PLAN,  Visibility.PRIVATE),
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
