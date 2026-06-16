"""
把一个 agent 的感知,拼成喂给 LLM 的 prompt。
"""
from __future__ import annotations

from dataclasses import dataclass
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
    '{"action":"act","content":"我此刻做出来的动作——在场的人都看得见的身体举动或对身边东西的摆弄,不是开口说话"}\n'
    '{"action":"move","destination":"<我要去的地点 id,必须是下文列出的那几个之一>"}\n'
    "\n"
    "如果我这一刻打定主意要走,就专心走——脚一旦迈出去,话还没出口,手头的事也来不及做。\n"
    "所以这一刻里要么我留下、要么我离开:走的话就只配 move,顶多再加心里掠过的念头(think)和心里盘算(plan),不要再混 speak / act。等到了新地方,下一刻再开口、再动手。\n"
)


@dataclass
class ParsedAction:
    action_type: ActionType
    visibility: Visibility
    content: str
    destination_id: str | None = None


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

    # —— 4. 此刻——只在确有可感知的事件时才铺;无事发生就不要硬塞"安静"
    #              ——以免让 LLM 误读成"大家在等我开口"的张力。
    if perception.visible_events:
        id_to_name = {other.id: other.name for other in perception.others_present}
        id_to_name[me.id] = me.name
        lines.append("")
        lines.append("就在此刻——")
        for e in perception.visible_events:
            speaker = id_to_name.get(e.actor_id, e.actor_id)
            if e.type == ActionType.SPEAK:
                lines.append(f"我听见{speaker}说:「{e.content}」")
            elif e.type == ActionType.ACT:
                lines.append(f"我看见{speaker}:{e.content}")
            elif e.type == ActionType.MOVE:
                # content 已是模板化的"X 离开了,去往 Y" 或 "X 来到了 Y"
                lines.append(f"我看见{e.content}")

    # —— 5. 我此刻知道还能去的地方(若要 MOVE,destination 必须取这里的 id) ——
    if perception.location_catalog:
        here_id = me.location_id
        lines.append("")
        lines.append(f"我此刻人在「{perception.location_catalog[here_id].name}」({here_id})。我知道还能去这几个地方——")
        for loc in perception.location_catalog.values():
            if loc.id == here_id:
                continue
            lines.append(f"- {loc.id}({loc.name}):{loc.description}")

    return "\n".join(lines)


# 动作种类 → (ActionType, Visibility)。
_ACTION_MAP = {
    "speak": (ActionType.SPEAK, Visibility.PUBLIC),
    "think": (ActionType.THINK, Visibility.PRIVATE),
    "plan":  (ActionType.PLAN,  Visibility.PRIVATE),
    "move":  (ActionType.MOVE,  Visibility.PUBLIC),
    "act":   (ActionType.ACT,   Visibility.PUBLIC),
}


def parse_response(raw: str) -> list[ParsedAction]:
    """
    解析 LLM response,可能含【多个】动作对象(各占一行的裸对象)。
    返回一个列表;整体一个都没解析出来时,兜底成【一条】 PRIVATE 心声(用 list 包着)。

    MOVE 走 "destination" 字段(目标地点 id),不强制 "content"。
    其它动作走 "content" 字段(空串会被跳过)。
    """
    results: list[ParsedAction] = []
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
            action_type, visibility = _ACTION_MAP[action]
            if action_type == ActionType.MOVE:
                destination = str(data.get("destination", "")).strip()
                if destination:
                    results.append(ParsedAction(action_type, visibility, "", destination))
            else:
                content = str(data.get("content", "")).strip()
                if content:
                    results.append(ParsedAction(action_type, visibility, content))
        except (KeyError, ValueError):
            pass

        idx = raw.find("{", end)
    if not results:
        results.append(
            ParsedAction(ActionType.THINK, Visibility.PRIVATE, f"(解析失败)原文:{raw.strip()}")
        )
        return results

    # MOVE 独占一拍:含 MOVE 时,只保留首条 MOVE + 所有 THINK / PLAN,
    # 丢弃 SPEAK / ACT 和多余的 MOVE。绕开 brain.decide 在 me.location_id 上的统一盖章。
    if any(a.action_type == ActionType.MOVE for a in results):
        filtered: list[ParsedAction] = []
        move_kept = False
        for a in results:
            if a.action_type == ActionType.MOVE:
                if not move_kept:
                    filtered.append(a)
                    move_kept = True
            elif a.action_type in (ActionType.THINK, ActionType.PLAN):
                filtered.append(a)
            # SPEAK / ACT:丢弃
        results = filtered

    return results


if __name__ == "__main__":
    cases = [
        '{"action": "speak", "content": "海报我来弄"}',
        '{"action":"think","content":"得想想"}\n{"action":"speak","content":"加油"}',
        '```json\n{"action":"think","content":"嗯"}\n```',
        '好的:{"action":"speak","content":"走"}',
        '我觉得我该说点什么',
        '{"action":"move","destination":"rooftop"}',
        '{"action":"move","destination":"rooftop"}\n{"action":"think","content":"我得静一静"}',
        # 独占一拍:move + speak + think → 只剩 move + think
        '{"action":"move","destination":"rooftop"}\n{"action":"speak","content":"我先走了"}\n{"action":"think","content":"得躲躲"}',
        # 独占一拍:两条 move + plan → 只剩首条 move + plan
        '{"action":"move","destination":"rooftop"}\n{"action":"move","destination":"hallway"}\n{"action":"plan","content":"先去天台再说"}',
    ]
    for c in cases:
        print(parse_response(c))
