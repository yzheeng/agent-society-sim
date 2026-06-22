"""社会模拟 · 核心数据模型(第一步 / MVP)

设计原则:引擎只认识下面这些【通用】结构;具体"主题"(人物、地点)
都是喂进来的【数据】。将来想换世界观,只替换文件最底下的数据部分,
上面的引擎代码一行都不用动。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .enums import ActionType, Visibility
from .clock import Calendar

# 导演层注入的"外部火种"事件的 actor_id。不对应任何 agent——
# 它代表"世界本身"发生的事(手机震动、撞见、广播通知……),
# 由 perceive() 的 PUBLIC + 同 location 过滤自然送达在场 agent。
# 渲染侧(prompts / memory)凭这个哨兵把它当旁白处理,不去 agents 里查名字。
WORLD_ACTOR = "_world_"

@dataclass
class Location:
    id: str
    name: str
    description: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description}

    @classmethod
    def from_dict(cls, d: dict) -> "Location":
        return cls(id=d["id"], name=d["name"], description=d.get("description", ""))


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
    destination_id: str | None = None  # 仅 MOVE 用:目的地点 id;其它动作留空

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "actor_id": self.actor_id,
            "type": self.type.value,
            "content": self.content,
            "location_id": self.location_id,
            "targets": self.targets,
            "visibility": self.visibility.value,
            "destination_id": self.destination_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(
            tick=d["tick"],
            actor_id=d["actor_id"],
            type=ActionType(d["type"]),
            content=d["content"],
            location_id=d["location_id"],
            targets=list(d.get("targets", [])),
            visibility=Visibility(d.get("visibility", Visibility.PUBLIC.value)),
            destination_id=d.get("destination_id"),
        )


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

    # —— 信念:导演"植入"的持久认知,长留在自我里,每拍都给行为染色。
    #    与 impulses(转瞬冲动)相对,这是【持久】的——进 to_dict/from_dict,跨重启存活。
    beliefs: list[str] = field(default_factory=list)

    # —— 关系:对其他 agent 的好感 / 信任,-100..100 —— 这就是"摩擦"的量化
    relationships: dict[str, int] = field(default_factory=dict)

    # —— 印象:对其他 agent 的一句话私下看法(定性),由反思从经历里长出来。
    #    与 relationships(好感数值)互补:一个是"我觉得他是个什么人",一个是"我对他几分亲疏"。
    impressions: dict[str, str] = field(default_factory=dict)

    # —— 记忆:先用最朴素的字符串列表,跑通后再升级成你那套短/长期记忆 ——
    memory: list[str] = field(default_factory=list)

    # —— 临时冲动:导演"私语"塞进来的念头,只在【下一次行动】时以"突如其来的念头"
    #    醒目浮现,消费即清。刻意【不持久化】(不进 to_dict/from_dict)——它是转瞬的
    #    此刻冲动,不是长期记忆,跨重启丢失可接受。
    impulses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "location_id": self.location_id,
            "public_persona": self.public_persona,
            "private_goal": self.private_goal,
            "secret": self.secret,
            "plan": self.plan,
            "beliefs": list(self.beliefs),
            "relationships": dict(self.relationships),
            "impressions": dict(self.impressions),
            "memory": list(self.memory),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Agent":
        return cls(
            id=d["id"],
            name=d["name"],
            location_id=d["location_id"],
            public_persona=d["public_persona"],
            private_goal=d["private_goal"],
            secret=d["secret"],
            plan=d.get("plan", ""),
            beliefs=list(d.get("beliefs", [])),
            relationships=dict(d.get("relationships", {})),
            impressions=dict(d.get("impressions", {})),
            memory=list(d.get("memory", [])),
        )


@dataclass
class WorldState:
    """整个世界的唯一事实来源。

    calendar 由 scenario 装配时挂上,不持久化——scenario 代码是它的 source of truth,
    每次 load 后由调用方重新挂回去。
    """
    tick: int = 0
    agents: dict[str, Agent] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    event_log: list[Event] = field(default_factory=list)
    calendar: Calendar | None = None

    def agents_at(self, location_id: str) -> list[Agent]:
        """某地点此刻在场的 agent —— 下一步的感知过滤会用到它。"""
        return [a for a in self.agents.values() if a.location_id == location_id]

    def to_meta_dict(self) -> dict:
        """只 dump 元状态(tick / locations);agents 和 event_log 分文件存。
        calendar 不存——它是 scenario 配置,由调用方重新挂上。"""
        return {
            "tick": self.tick,
            "locations": {lid: loc.to_dict() for lid, loc in self.locations.items()},
        }
