"""brain 决策层的工具能力清单。

把每个 ActionType 注册成一个 OpenAI Chat Completions 兼容的 tool,
让 LLM 在 API 层就只能输出合法 action,不再靠自然语言 prompt 约束。

跟 prompts.py(拼自然语言独白)、brain.py(决策流程)职责清晰分开 ——
未来加新 ActionType / 调 tool schema,只动这一个文件。
"""
from __future__ import annotations

from society.core.perception import Perception


def build_tools(perception: Perception) -> list[dict]:
    """根据当前感知动态生成 5 个 tool。

    move 的 destination 用 enum 限制为「除当前位置外的所有可达地点」,
    API 层自然挡掉非法目的地,brain 不再需要二次校验。
    """
    me = perception.self_agent
    move_targets = [lid for lid in perception.location_catalog if lid != me.location_id]

    def fn(name: str, desc: str, params: dict) -> dict:
        return {"type": "function", "function": {"name": name, "description": desc, "parameters": params}}

    string_content = {
        "type": "object",
        "properties": {"content": {
            "type": "string",
            "description": "一段连续文字,不要换行,不要分段,不要用 - 项目符号或任何 markdown 格式",
        }},
        "required": ["content"],
    }

    return [
        fn("speak", "我此刻当众说出口的话,在场的人都听得见", string_content),
        fn("think", "我此刻心里默默掠过的念头,谁也听不到", string_content),
        fn("plan",  "我此刻心里盘算的下一步——眼前心思,等会儿会随情况再变。一回合至多一条。", string_content),
        fn("act",   "我此刻做出来的动作——在场的人都看得见的身体举动或对身边东西的摆弄,不是开口说话", string_content),
        fn("silence",
           "我此刻当众按下话头,什么也不说、不动——这不是没反应,是我有意把话咽回去、把动作收住。"
           "在场的人会看见我沉默。只有当我此刻确实选择以静默来回应(忍着、僵着、不愿搭理、心虚不敢应)时才用它;"
           "若我心里有任何想说想做的,就去 speak / act,别拿沉默搪塞。",
           {"type": "object", "properties": {}, "required": []}),
        fn("move",  "我离开此地,去往别处。脚一旦迈出去就专心走,这一刻不能再 speak / act。",
            {"type": "object",
             "properties": {
                 "destination": {
                     "type": "string",
                     "enum": move_targets,
                     "description": "我要去的地点 id",
                 }
             },
             "required": ["destination"]}),
    ]
