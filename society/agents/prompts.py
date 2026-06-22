"""
把一个 agent 的感知,拼成喂给 LLM 的 prompt(第一人称内独白)。

LLM 实际能"做"什么,由 society/agents/tools.py 在 API 层声明并强制;
这里只负责把"我此刻是谁、看到了什么、记得什么"翻译成自然语言。

—— 分层模型(自上而下 = 自背景到前景)————————————————————————
prompt 越靠后,模型注意力越重(近因效应)。所以刻意按"稳定 → 易变"排布,
把最新、最该牵动我的刺激压在全文最末,拿最高权重:

  第1层 身份·事实层   我是谁、人前的样子、深层欲求、藏着的秘密      (最稳定)
  第2层 认知·透镜层   beliefs:已认定挥不去的事,给一切解读打底色
  第3层 意图层        plan:当前短期打算——"没出岔子时"的默认路线
  第4层 记忆层        recalled:脑子里还回响的经历片段(背景记忆)
  第5层 处境层        此刻的时间 / 在场的人 / 能去的地方
  第6层 此刻骤变层    visible_events:身边刚发生的公开事件
  第7层 冲动注入层    impulses:导演私语塞进来的转瞬念头              (最高权重)

配合 SYSTEM_PROMPT 里"最新最扎眼的事盖过原计划"的指令,让靠后的火种 /
私语 / 骤变真能扭转行动,而不被靠前的长 plan 和旧记忆淹掉。

注:goal / secret 虽属深层动机 / 事实,但与 persona 同处第1层——三者"人前
一套、心里一套、还藏着一手"的对照本身就是戏剧张力的核心,刻意揉成一段自述
不拆开。plan 同理放在靠前的"静态的我"里:它是默认路线,刻意低权重,好让靠后
的骤变按近因把它盖过。
"""
from __future__ import annotations

from collections.abc import Sequence

from society.core.perception import Perception
from society.core.enums import ActionType
from society.core.models import WORLD_ACTOR
from society.core.clock import decompose, days_remaining


SYSTEM_PROMPT = (
    "下面那段文字里的「我」就是你这个人——这个人的过往、心思、藏着的事、此刻的感官,都是你自己的,不是你在演谁。\n"
    "请以「我」的口吻,如实写下此刻的反应。不要解释,不要在第三方视角上点评自己,不要写「作为某某我...」这样的话。\n"
    "\n"
    "我此刻的反应——说出口的话、动作、心声、盘算、走开——都得落到我手头能做的那几件事上;脑子里转一转又收回来不算,得真切地「做」出来。脑子里飘过一圈又收回去、什么都没真做,是不被接受的——哪怕只是手指头叩一下桌面、心里默念一声、嘴里轻轻嗯一句,也得有一件落到实处。\n"
    "\n"
    "我此刻的反应不必只挑一件来做——手上一个小动作、嘴里一句话、心里掠过的一个念头、心底的一句盘算,本就可能同时在发生。该有几样就落几样,别为了凑数硬塞,也别为了简洁漏掉;每一件就只说它自己,不要把动作、心声、盘算搅在一段里讲。\n"
    "\n"
    "我心里或许早有打算,但眼前的世界是活的:此刻若身边骤然出了什么事、或一个念头毫无预兆地攫住我,我的反应会先冲着这件最新、最扎眼的事去,而不是闷头照原样把老主意走完。打算是为了我真正想要的东西服务的,不是拿来对眼前的变化视而不见的——越是出乎意料、越是戳到我的事,越会牵着我接下来怎么说、怎么做,该变就变,甚至当场推翻原本的盘算。绝不要把刚发生的事轻轻一带而过、然后照旧重复我上一刻说过做过的话。\n"
    "\n"
    "如果我这一刻打定主意要走,就专心走——脚一旦迈出去,话还没出口,手头的事也来不及做。\n"
    "所以这一刻里要么我留下、要么我离开:走的话就只用 move,顶多再加心里掠过的念头(think)和心里盘算(plan),不要再混 speak / act。等到了新地方,下一刻再开口、再动手。\n"
)


def build_user_prompt(
    perception: Perception,
    recalled: list[str],
    impulses: Sequence[str] = (),
) -> str:
    """把感知拼成一段角色的第一人称内独白,以「我」的口吻自然展开。

    impulses:导演"私语"塞进来的转瞬念头,放在全文最末以最高权重呈现。
    """
    me = perception.self_agent

    # ════ 第1层 · 身份·事实层 ════════════════════════════════════════════
    # 我是谁:人前的样子(公开)+ 深层欲求 + 藏着的秘密(私密)。最稳定,放最前。
    # 三者揉成一段第一人称自述,不打分层标签——"人前一套 / 心里一套 / 藏着一手"
    # 的对照本身就是戏剧张力,刻意不拆。
    lines = [
        f"我是{me.name}。",
        f"人前的我,{me.public_persona}。",
        f"可我心里真正想要的,是{me.private_goal}。",
        f"我藏着没让任何人知道的事:{me.secret}。",
    ]

    # ════ 第2层 · 认知·透镜层 ════════════════════════════════════════════
    # beliefs:已经认定、挥不去的事,长留在自我里,给一切解读打底色(看人看事的眼光)。
    if me.beliefs:
        lines.append("有些事我心里早已认定,挥之不去,左右着我看人看事的眼光:")
        lines.extend(f"- {b}" for b in me.beliefs)

    # ════ 第3层 · 意图层 ═════════════════════════════════════════════════
    # plan:当前短期打算 = "没出岔子时"的默认路线。刻意放靠前(低近因权重),
    # 好让后面的骤变 / 私语按近因把它盖过——给推翻它留出余地。
    if me.plan:
        lines.append(f"我本来盘算着:{me.plan}——不过那是没出岔子时的打算。")

    # ════ 第4层 · 记忆层 ═════════════════════════════════════════════════
    # recalled:脑子里还回响的经历片段(背景记忆,只有我自己记得)。
    # 位置在"静态的我"之后、"此刻处境"之前——背景记忆垫在骤变前,符合
    # "静态的我 → 背景记忆 → 此刻骤变"的排布。物理长度由 compression 兜底。
    if recalled:
        lines.append("")
        lines.append("我脑子里还回响着这些片段(只有我自己记得):")
        lines.extend(f"- {m}" for m in recalled)

    # ════ 第5层 · 处境层 ═════════════════════════════════════════════════
    # 此刻这一拍的客观背景:时间感 / 在场的人 / 能去的地方。比记忆新、比骤变旧。

    # 5a. 时间感(只翻译,不暴露机制:不说 phase / tick / 第几拍)。
    if perception.calendar is not None:
        day, phase, _ = decompose(perception.tick, perception.calendar)
        remaining = days_remaining(perception.tick, perception.calendar)
        lines.append("")
        lines.append(f"今天是第 {day} 天,{phase}。")
        if remaining == 0:
            lines.append(f"{perception.calendar.terminal_event}就在今日。")
        else:
            lines.append(f"距{perception.calendar.terminal_event}还有 {remaining} 天。")

    # 5b. 此刻四周还有谁在场——只看得到他们摆给所有人看的那一面(公开层)。
    if perception.others_present:
        lines.append("")
        lines.append("我抬眼环顾四周——")
        for other in perception.others_present:
            line = f"{other.name}也在,在所有人眼里是「{other.public_persona}」。"
            # 私下印象:由反思从过往经历里长出来(impressions),只有我自己知道,
            # 叠在对方的公开面之上——人前一套、我心里另有掂量。
            impression = me.impressions.get(other.id)
            if impression:
                line += f"——可打过这些交道,我私下里觉得:{impression}"
            lines.append(line)
        lines.append("我跟他们打交道,看到的是他们摆给所有人看的那一面,可我心里自有一杆秤。")
    else:
        lines.append("")
        lines.append("此刻这儿就我一个,周围没别人。")

    # 5c. 此刻知道还能去的地方(供 move 工具参考;tools 那边也用 enum 锁死了合法值)。
    #     放在"此刻骤变"之前——把最新的刺激留到全文最末,拿最高权重。
    if perception.location_catalog:
        here_id = me.location_id
        lines.append("")
        lines.append(f"我此刻人在「{perception.location_catalog[here_id].name}」({here_id})。我知道还能去这几个地方——")
        for loc in perception.location_catalog.values():
            if loc.id == here_id:
                continue
            lines.append(f"- {loc.id}({loc.name}):{loc.description}")

    # ════ 第6层 · 此刻骤变层 ═════════════════════════════════════════════
    # visible_events:身边刚发生的公开事件。只在确有可感知事件时才铺;无事发生
    # 不硬塞"安静"——以免让 LLM 误读成"大家在等我开口"的张力。
    if perception.visible_events:
        id_to_name = {other.id: other.name for other in perception.others_present}
        id_to_name[me.id] = me.name
        lines.append("")
        lines.append("就在此刻,身边发生了——")
        for e in perception.visible_events:
            if e.actor_id == WORLD_ACTOR:
                # 外部火种:不是谁说的、谁做的,是世界本身骤然发生的事,当旁白直接铺。
                lines.append(e.content)
                continue
            speaker = id_to_name.get(e.actor_id, e.actor_id)
            if e.type == ActionType.SPEAK:
                lines.append(f"我听见{speaker}说:「{e.content}」")
            elif e.type == ActionType.ACT:
                lines.append(f"我看见{speaker}:{e.content}")
            elif e.type == ActionType.MOVE:
                # content 已是模板化的"X 离开了,去往 Y" 或 "X 来到了 Y"
                lines.append(f"我看见{e.content}")

    # ════ 第7层 · 冲动注入层 ═════════════════════════════════════════════
    # impulses:导演"私语"塞进来的转瞬念头。全文最末,权重最高,挥之不去——
    # 它和 private_goal 同属动机轴,只是 goal 是常年引力、impulse 是这一秒的尖峰。
    if impulses:
        lines.append("")
        for imp in impulses:
            lines.append(f"就在这时,一个念头毫无预兆地攫住了我,挥之不去——{imp}")

    return "\n".join(lines)
