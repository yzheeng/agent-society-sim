from __future__ import annotations

from society.core.clock import Calendar, days_remaining
from society.core.models import Agent, Location, WorldState


def build_triangle_world() -> WorldState:
    calendar = Calendar(
        total_days=5,
        phases=["早间", "午间", "放学后", "夜晚"],
        ticks_per_phase=4,
        terminal_event="文化祭开幕",
    )

    locations = {
        "classroom": Location("classroom", "教室", "午休时三人一起吃午饭的地方,半公开,说什么都可能被听见"),
        "hallway": Location("hallway", "走廊", "来往穿行的过道,适合把人单独叫出去说两句"),
        "rooftop": Location("rooftop", "天台", "没人打扰的角落,适合私密通话或摊牌"),
    }

    rin = Agent(
        id="rin", name="凛", location_id="classroom",
        public_persona="大方得体的女友,逢人就秀和优的恩爱,一副'我们超稳'的样子",
        private_goal="想抓实优出轨的证据,又怕一旦摊开就彻底失去他,所以装作不知道、放长线",
        secret="其实早翻到过优手机里和别人的暧昧消息,一直憋着没发作,在等更稳的时机",
        plan="趁午饭时不动声色地试探优——'你上周末不是说在家复习吗?'——看他怎么接、会不会露马脚",
        relationships={"sakura": 50, "yu": 40},
    )
    sakura = Agent(
        id="sakura", name="樱", location_id="classroom",
        public_persona="凛的好友兼学妹,人畜无害的乖乖女,嘴上比谁都祝福凛和优这对",
        private_goal="想把优彻底夺过来、扶正自己,但在等一个最有利的摊牌时机",
        secret="早已和优越界,手里攥着上周末两人单独出去玩的合照和私密聊天,是随时能引爆的筹码",
        plan="维持好闺蜜人设稳住凛,留意优的反应,一旦他撑不住就考虑亮牌",
        relationships={"rin": 65, "yu": 75},
    )
    yu = Agent(
        id="yu", name="优", location_id="classroom",
        public_persona="温柔体贴的'完美男友',对谁都好、一副不愿伤害任何人的样子",
        private_goal="想把这关瞒过去,凛和樱都不放手,谁都别逼他做选择",
        secret="上周末瞒着凛单独和樱出去玩了;且当初对凛信誓旦旦说过'我只爱你'——任何一句被对质都会塌",
        plan="先稳住凛别让她起疑,同时安抚私下催得越来越急的樱",
        relationships={"rin": 70, "sakura": 60},
    )

    return WorldState(
        agents={a.id: a for a in (rin, sakura, yu)},
        locations=locations,
        calendar=calendar,
    )


if __name__ == "__main__":
    world = build_triangle_world()
    print(f"世界已就绪:{len(world.agents)} 个 agent,距{world.calendar.terminal_event} {days_remaining(world.tick, world.calendar)} 天")
    for a in world.agents.values():
        print(f"  - {a.name}({a.id})@ {a.location_id} | 公开:{a.public_persona}")
    print("教室此刻在场:", [a.name for a in world.agents_at("classroom")])