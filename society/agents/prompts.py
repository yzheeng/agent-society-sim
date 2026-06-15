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


def build_user_prompt(perception: Perception) -> str:
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

    # —— 3. 我看见/听到了什么——
    if perception.visible_events:
        lines.append("\n【你看到/听到的】")
        for e in perception.visible_events:
            lines.append(f"- {e.actor_id}:{e.content}")
    else:
        lines.append("\n【周围很安静,没有发生什么】")

    # —— 4. 要它干什么:只用 JSON 回应,动作种类 + 内容 ——
    lines.append(
        "\n现在请只用 JSON 回应,不要任何解释、旁白或代码围栏。\n"
        "这一回合你只能做一个动作,因此只输出一个 JSON 对象,格式严格如下:\n"
        '{"action": "speak 或 think", "content": "你要说的话 / 心里想的内容"}\n'
        "speak = 你当众说出口的话;think = 只有你自己知道的心声。"
    )

    return "\n".join(lines)


# 动作种类 → (ActionType, Visibility)。
_ACTION_MAP = {
    "speak": (ActionType.SPEAK, Visibility.PUBLIC),
    "think": (ActionType.THINK, Visibility.PRIVATE),
}


def parse_response(raw: str) -> tuple[ActionType, Visibility, str]:
    """
    解析llm response
    解析失败时兜底成一句 PRIVATE 心声。
    """
    try:
        body = raw[raw.index("{"): raw.rindex("}") + 1]
        data = json.loads(body)

        action = str(data["action"]).strip().lower()
        content = str(data["content"]).strip()
        action_type, visibility = _ACTION_MAP[action]
        if not content:
            raise ValueError("content 为空")
        return action_type, visibility, content

    except (ValueError, KeyError, json.JSONDecodeError):
        # 兜底:当作心声(PRIVATE),不污染公开广播;原文带出来,上帝视角好排查
        return ActionType.THINK, Visibility.PRIVATE, f"(解析失败)原文:{raw.strip()}"


if __name__ == "__main__":
    cases = [
        '{"action": "speak", "content": "海报我来弄"}',
        '```json\n{"action":"think","content":"得想想办法"}\n```',
        '好的,这是我的回应:{"action":"speak","content":"加油"}',
        '我觉得我该说点什么',
    ]
    for c in cases:
        print(parse_response(c))
