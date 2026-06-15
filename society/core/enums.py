from enum import Enum


class Visibility(Enum):
    """一个事件谁能感知到。"""
    PUBLIC = "public"    # 同一地点的所有 agent 都能感知
    PRIVATE = "private"  # 只有当事 agent 自己 + 开发者(上帝)看得到


class ActionType(Enum):
    """agent 一回合能做的动作种类。"""
    SPEAK = "speak"  # 说话
    MOVE = "move"    # 移动到别的地点
    ACT = "act"      # 对世界做点什么(贴海报、送东西……)
    THINK = "think"  # 内心活动 —— 永远是 PRIVATE
    PLAN = "plan"    # 调整自己的"眼下打算" —— 永远是 PRIVATE,落子时写回 agent.plan