"""
把一个 agent 的感知,拼成喂给 LLM 的 prompt(第一人称内独白)。

LLM 实际能"做"什么,由 society/agents/tools.py 在 API 层声明并强制;
这里只负责把"我此刻是谁、看到了什么、记得什么"翻译成自然语言。
"""
from __future__ import annotations

from society.engine.perception import Perception
from society.core.enums import ActionType
from society.core.clock import decompose, days_remaining


SYSTEM_PROMPT = (
    "下面那段文字里的「我」就是你这个人——这个人的过往、心思、藏着的事、此刻的感官,都是你自己的,不是你在演谁。\n"
    "请以「我」的口吻,如实写下此刻的反应。不要解释,不要在第三方视角上点评自己,不要写「作为某某我...」这样的话。\n"
    "\n"
    "我此刻的反应——说出口的话、动作、心声、盘算、走开——都得落到我手头能做的那几件事上;脑子里转一转又收回来不算,得真切地「做」出来。脑子里飘过一圈又收回去、什么都没真做,是不被接受的——哪怕只是手指头叩一下桌面、心里默念一声、嘴里轻轻嗯一句,也得有一件落到实处。\n"
    "\n"
    "我此刻的反应不必只挑一件来做——手上一个小动作、嘴里一句话、心里掠过的一个念头、心底的一句盘算,本就可能同时在发生。该有几样就落几样,别为了凑数硬塞,也别为了简洁漏掉;每一件就只说它自己,不要把动作、心声、盘算搅在一段里讲。\n"
    "\n"
    "如果我这一刻打定主意要走,就专心走——脚一旦迈出去,话还没出口,手头的事也来不及做。\n"
    "所以这一刻里要么我留下、要么我离开:走的话就只用 move,顶多再加心里掠过的念头(think)和心里盘算(plan),不要再混 speak / act。等到了新地方,下一刻再开口、再动手。\n"
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

    # —— 2. 时间感(只翻译,不暴露机制:不说 phase / tick / 第几拍) ——
    if perception.calendar is not None:
        day, phase, _ = decompose(perception.tick, perception.calendar)
        remaining = days_remaining(perception.tick, perception.calendar)
        lines.append("")
        lines.append(f"今天是第 {day} 天,{phase}。")
        if remaining == 0:
            lines.append(f"{perception.calendar.terminal_event}就在今日。")
        else:
            lines.append(f"距{perception.calendar.terminal_event}还有 {remaining} 天。")

    # —— 3. 此刻四周 ——
    if perception.others_present:
        lines.append("")
        lines.append("我抬眼环顾四周——")
        for other in perception.others_present:
            lines.append(f"{other.name}也在,在所有人眼里是「{other.public_persona}」。")
        lines.append("我跟他们打交道,看到的也就是他们摆给所有人看的那一面。")
    else:
        lines.append("")
        lines.append("此刻这儿就我一个,周围没别人。")

    # —— 4. 我脑子里还回响着的 ——
    if recalled:
        lines.append("")
        lines.append("我脑子里还回响着这些片段(只有我自己记得):")
        lines.extend(f"- {m}" for m in recalled)

    # —— 5. 此刻——只在确有可感知的事件时才铺;无事发生就不要硬塞"安静"
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

    # —— 6. 我此刻知道还能去的地方(供 move 工具参考;tools 那边也用 enum 锁死了合法值) ——
    if perception.location_catalog:
        here_id = me.location_id
        lines.append("")
        lines.append(f"我此刻人在「{perception.location_catalog[here_id].name}」({here_id})。我知道还能去这几个地方——")
        for loc in perception.location_catalog.values():
            if loc.id == here_id:
                continue
            lines.append(f"- {loc.id}({loc.name}):{loc.description}")

    return "\n".join(lines)
