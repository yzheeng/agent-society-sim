"""社会模拟 · 核心数据模型(第一步 / MVP)

设计原则:引擎只认识下面这些【通用】结构;具体"主题"(人物、地点)
都是喂进来的【数据】。将来想换世界观,只替换文件最底下的数据部分,
上面的引擎代码一行都不用动。
"""
from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class Event:
    """世界里发生的一件事。整条 event_log 就是这个世界的全部历史,
    也是 TUI 渲染、感知过滤、复现回放共同的数据来源。"""
    tick: int                  # 第几回合发生
    actor_id: str              # 谁触发的
    type: ActionType
    content: str               # 说了 / 做了 / 想了什么
    location_id: str           # 在哪儿发生
    targets: list[str] = field(default_factory=list)      # 指向谁(可空)
    visibility: Visibility = Visibility.PUBLIC


@dataclass
class Agent:
    """一个角色。注意公开层和私密层是【分开】存的 ——
    这道分隔正是后面感知过滤、以及'嘴上一套心里一套'戏剧性的来源。"""
    id: str
    name: str
    location_id: str

    # —— 公开层:别人能看到的 ——
    public_persona: str

    # —— 私密层:只有它自己 + 上帝知道 ——
    private_goal: str          # 它真正想要的
    secret: str                # 被戳破会出事的东西
    plan: str = ""             # 当前短期打算,每回合可更新

    # —— 关系:对其他 agent 的好感 / 信任,-100..100 —— 这就是"摩擦"的量化
    relationships: dict[str, int] = field(default_factory=dict)

    # —— 记忆:先用最朴素的字符串列表,跑通后再升级成你那套短/长期记忆 ——
    memory: list[str] = field(default_factory=list)


@dataclass
class Location:
    id: str
    name: str
    description: str = ""


@dataclass
class WorldState:
    """整个世界的唯一事实来源。"""
    tick: int = 0
    days_until_festival: int = 7  # 主线时钟:到 0 就是文化祭,逼所有人摊牌
    agents: dict[str, Agent] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    event_log: list[Event] = field(default_factory=list)

    def agents_at(self, location_id: str) -> list[Agent]:
        """某地点此刻在场的 agent —— 下一步的感知过滤会用到它。"""
        return [a for a in self.agents.values() if a.location_id == location_id]


# ==========================================================================
# 以下是【临时主题】—— 纯数据。将来整块搬进 config / JSON 替换即可。
# 樱丘高中 · 文化祭前一周
# ==========================================================================

def build_campus_world() -> WorldState:
    locations = {
        "classroom": Location("classroom", "1年A班教室", "大家日常待的地方"),
        "rooftop": Location("rooftop", "天台", "适合说悄悄话的地方"),
        "clubroom": Location("clubroom", "社团活动室", "文化祭筹备的据点"),
    }

    akari = Agent(
        id="akari", name="桐谷灯里", location_id="classroom",
        public_persona="认真负责的班长,一心想把文化祭办成功",
        private_goal="借文化祭的表现拿到推荐名额,证明自己",
        secret="最近成绩在下滑,很怕被人发现",
        relationships={"sota": 30, "mei": 60},
    )
    sota = Agent(
        id="sota", name="凉宫宗太", location_id="classroom",
        public_persona="吊儿郎当爱开玩笑,总跟班长唱反调",
        private_goal="想接近灯里,却用捣乱来掩饰",
        secret="偷偷在帮筹备组做东西,藏着没说出口的才能",
        relationships={"akari": 70, "mei": 40},
    )
    mei = Agent(
        id="mei", name="七海芽衣", location_id="rooftop",
        public_persona="安静的转学生,话不多",
        private_goal="想融入班级、交到朋友",
        secret="无意中撞见了灯里成绩下滑的事,正纠结要不要说出去",
        relationships={"akari": 50, "sota": 45},
    )

    return WorldState(
        days_until_festival=7,
        agents={a.id: a for a in (akari, sota, mei)},
        locations=locations,
    )


if __name__ == "__main__":
    world = build_campus_world()
    print(f"世界已就绪:{len(world.agents)} 个 agent,距文化祭 {world.days_until_festival} 天")
    for a in world.agents.values():
        print(f"  - {a.name}({a.id})@ {a.location_id} | 公开:{a.public_persona}")
    print("教室此刻在场:", [a.name for a in world.agents_at("classroom")])
