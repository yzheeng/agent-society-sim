# ==========================================================================
# 以下是【临时主题】—— 纯数据。将来整块搬进 config / JSON 替换即可。
# 樱丘高中 · 文化祭前一周
# ==========================================================================
from __future__ import annotations

from society.core.models import Agent, Location, WorldState

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
