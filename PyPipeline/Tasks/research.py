"""博物研学：把旧流水线里 5 个 JSON 合并成一个任务模块。

移植自 ``assets/resource_picli/base/pipeline/`` 下的：

* ``11_Research.json``（13 节点）—— 入口、主题分支、地图分支
* ``11_2_goldresearch.json``（62 节点）—— 金银纪行的选人 / 营地 / 战斗
* ``11_(02)_snowscape.json``（132 节点）—— 雪景寒林图（全项目最大的一张图）
* ``11_(03)_landscape.json``（2 节点）—— 千里江山图
* ``11_(04)_journey.json``（2 节点）—— 溪山旅行图

旧实现的三处「绕圈」在这里都被拆掉了：

1. ``choose_theme`` / ``mountain_Research`` / ``gold_research`` 是三个「没有识别、
   只等着被 ``interface.json`` 的 ``pipeline_override`` 换掉 ``next``」的占位节点。
   现在它们就是函数里的一个查表：见 :func:`选择研学主题`、:func:`按地图分流`、
   :func:`走金银纪行`（旧 ``gold_research`` 的 next 被换掉的那个地方）。
2. 每个节点的 ``next`` 表（「反复试这几个识别，谁先命中就做谁」）直接写成
   ``ctx.scan(...)``；``[JumpBack]Exception-handling-*`` 收进 :func:`handle_exceptions`。
3. 旧实现用 ``event_select`` 这个自定义识别去读 ``assets/*/data/event.json`` 的随机事件
   表，而那个识别在 Python 侧从来没实现过。这里落成 :data:`事件选项` 字典 +
   :func:`选事件选项` 查表点击。

雪景寒林图里有 60 多个节点共用同一批「地图上能点什么」的 ``next`` 表（``advance_two`` /
``advance_three`` / ``advance_four`` 三张长表互相包含），逐节点照抄会变成无限递归；
这里把它们并成一张 :data:`地图表`，用一个 ``while`` 循环反复扫，命中的节点自己在表里
把动作做完 —— 和旧 pipeline 的「扫到谁做谁」等价。
"""

from __future__ import annotations

from typing import Optional, Sequence

from MWATools.MWATask import (
    IMG,
    OCR,
    Cand,
    Choice,
    Option,
    Step,
    TaskContext,
    handle_exceptions,
    task,
)

# --------------------------------------------------------------------- 选项
#
# 三个选项的 key / case 名 / 默认值都按 ``assets/interface.json`` 里
# task「博物研学」的 ``option`` 列表逐字对齐；默认值取旧配置的第一个 case。

主题_山水纪行 = "山水纪行"
主题_金银纪行 = "金银纪行"

地图_雪景寒林图 = "雪景寒林图"
地图_千里江山图 = "千里江山图 （暂无）"
地图_溪山旅行图 = "溪山旅行图 （暂无）"
地图_打新研学 = "打新研学选择"

手动_自己选 = "手动选择角色(选择完成，进入博学地图后才能开始运行)"
手动_自动 = "不手动选择，由MWA选择"

#: 旧节点 ``choose_theme`` 的 ``next`` 被这个选项覆盖成 ``mountain-river`` / ``gold-silver``。
主题选项 = Option(
    "选择研学主题",
    label="选择研学主题",
    kind="select",
    default=主题_山水纪行,
    choices=(Choice(主题_山水纪行), Choice(主题_金银纪行)),
    description="山水纪行走雪景寒林图，金银纪行是金色研学",
)

#: 旧节点 ``mountain_Research`` 的 ``next`` 被这个选项覆盖成一张地图。
地图选项 = Option(
    "选择地图(仅老研学)",
    label="选择地图(仅老研学)",
    kind="select",
    default=地图_雪景寒林图,
    choices=(
        Choice(地图_雪景寒林图),
        Choice(地图_千里江山图),
        Choice(地图_溪山旅行图),
        Choice(地图_打新研学),
    ),
    description="只对山水纪行有效；后两张图旧配置里写着「暂无」",
)

#: 旧节点 ``gold_research`` 的 ``next`` 被这个选项覆盖成「等玩家自己选」或「由 MWA 选」。
手动选项 = Option(
    "是否手动选择角色和buff",
    label="是否手动选择角色和buff",
    kind="select",
    default=手动_自己选,
    choices=(Choice(手动_自己选), Choice(手动_自动)),
    description="只对金银纪行有效",
)

# ----------------------------------------------------------------- 随机事件表
#
# 旧 ``event_select`` 自定义识别要读的那份表（``assets/resource/data/event.json`` 与
# ``assets/resource_picli/data/event.json``，37 条）。两份表 key 完全相同，其中有 12 条
# 文案不一样，所以值做成词表：先把 picli 包的文案放在前面，老包文案跟在后面，
# OCR 命中任意一条都算数。
#
# 另有几个旧节点写死的文案和两份表都对不上（例如 ``mysterious_2`` 认的是「打开」，
# 而表里是「当场打开」/「拆开」）——OCR 是按正则搜索匹配的，「打开」能匹配到
# 「当场打开」，所以不需要额外加词。
事件选项: dict[str, tuple[str, ...]] = {
    "神秘快递": ("当场打开", "拆开"),
    "科研助力": ("联系最近的基金会驻点询问相关事宜", "立刻联系附近基金会的驻点询问。"),
    "氧气瓶": ("抽！",),
    "画性大发": ("“正好，我带了画箱！”", "我正好有带"),
    "样本搜集": ("拿出采样工具进行采集", "拿出采样套装进行采集"),
    "群山之巅": ("拿出氧气瓶，继续前进", "拿出氧气瓶"),
    "手杖妙用": ("放下船桨，抓起背包侧面的登山杖去够衣物包", "抓起登山杖去够"),
    "珍贵笔记": ("还好有研学笔记本",),
    "寒雾": ("主动跟上那位器者。",),
    "风雪之途": ("与雪景寒林图喝茶。",),
    "山雪之约": ("前往常去的茶馆。",),
    "巡山雪": ("到路途中去。",),
    "再遇寒雪": ("顺势聊起山水画的事情。",),
    "山之形": ("潮流文化集市和商场。",),
    "青绿争端": ("安静地等待他。",),
    "小小风波": ("去符合心境的地方",),
    "幻梦成景": ("“非常有趣”的兴奋之情。",),
    "传达之声": ("尽自己所能推荐。",),
    "神秘传闻": ("寻找有人的落脚处。",),
    "山中之兽": ("由你调查消息来源。",),
    "出行必备": ("询问溪山行旅图的意见。",),
    "探索之夜": ("在野外扎营。",),
    "山间来信": ("你找错了地方？",),
    "浪漫收集": ("有人的地方就有故事", "去有故事的地方！"),
    "奇怪的画作": ("试着寻找草稿的主人吧", "找找草稿的主人吧。"),
    "线路规划": ("请她帮忙指一个方向", "请她帮忙指一个方向。"),
    "奇诡志异": ("和他们一起聊故事", "和他们一起聊故事。"),
    "游客照": ("向茶叶生产画请教技巧", "向茶叶生产画请教技巧。"),
    "时间与画": ("关于一日山景", "关于一日山景。"),
    "小心脚下": ("拿起来仔细观察",),
    "护林小屋": ("询问护林员",),
    "杂学之用": ("询问千里江山图",),
    "日出东山": ("来到民宿的屋顶",),
    "解惑": ("帮助回答",),
    "润水": ("上前询问",),
    "游学所得": ("讲旅行趣事",),
    "建议": ("提出你的想法",),
}


def 选事件选项(ctx: TaskContext, 事件名: str, *, 延时: int = 0, 后置冻结: int = 2000) -> bool:
    """查 :data:`事件选项`，点这个随机事件该选的选项。

    旧实现是 ``event_select`` 自定义识别（在 ``custom_demo.json`` 里被引用，Python 侧
    从未实现）。这里就是一次普通的字典查表 + OCR 点击；表里没有的事件名退回按事件名点。
    """
    词表 = 事件选项.get(事件名, (事件名,))
    return _点(
        ctx,
        OCR(
            list(词表),
            roi=事件选项区,
            delay=延时,
            wait_freezes=后置冻结,
            desc=f"事件「{事件名}」选：{词表[0]}",
        ),
    )


# ----------------------------------------------------------------- 区域常量
#
# 全部照抄旧 JSON 里的 ``roi``（1280x720 基准）。

#: 事件标题的 roi（旧 ``mist``/``Snow``/``cold_snow`` 等节点识别标题用）。
事件标题区 = (529, 65, 426, 104)
#: 事件选项的 roi（旧 ``*_2`` 节点点选项用）。
事件选项区 = (594, 351, 561, 279)
#: 主角（男 ``Research/84.png`` / 女 ``Research/85.png``）图标的 roi（旧 ``advance_*``）。
角色区 = (0, 0, 1280, 720)
#: 营地升级按钮 ``Research/16.png`` 的 roi（旧 ``upgrade_*``）。
升级按钮区 = (470, 83, 363, 142)
#: 升级/降阶确认弹窗 ``Research/17.png`` 的 roi（旧 ``choose*``）。
升级确认区 = (866, 530, 206, 81)
#: 战斗评价（中/良/优）的 roi（旧 ``war_two``/``war_three``/``war_four``）。
战斗评价区 = (500, 235, 270, 280)


# ----------------------------------------------------------------- 通用小工具


def _点(ctx: TaskContext, 候选: Cand, *, 前置冻结: int = 0) -> bool:
    """识别 → 点击。``前置冻结`` 对应旧节点的 ``pre_wait_freezes``。"""
    if 前置冻结:
        ctx.screen.wait_freezes(time=前置冻结)
    return ctx.tap(候选)


def _点图索引(
    ctx: TaskContext,
    图,
    *,
    roi: Optional[tuple[int, int, int, int]] = None,
    索引: int = 0,
    绿幕: bool = False,
    排序: str = "Horizontal",
    阈值: float = 0.7,
    前置冻结: int = 0,
    前置延时: int = 0,
    后置冻结: Optional[int] = None,
    延时: int = 0,
    偏移: Optional[tuple[int, int, int, int]] = None,
    desc: str = "",
) -> bool:
    """点模板图。

    ``index`` / ``green_mask`` / ``order_by`` / ``target_offset`` 这些 ``Cand``
    表达不了的参数在这里走 ``Screen`` 原语（旧 snowscape / goldresearch 里大量使用）。
    """
    if 前置延时:
        ctx.screen.sleep(前置延时)
    if 前置冻结:
        ctx.screen.wait_freezes(time=前置冻结)
    m = ctx.screen.find(图, roi=roi, threshold=阈值, green_mask=绿幕, order_by=排序, index=索引)
    if not m:
        return False
    return ctx.screen.click(m, offset=偏移, delay=延时, wait_freezes=后置冻结, desc=desc or f"点 {图}")


def _点坐标(ctx: TaskContext, x: int, y: int, *, 延时: int = 0, desc: str = "") -> bool:
    """直接点一个绝对坐标（旧 ``action: Click`` + ``target: [x, y, 0, 0]`` 且没有识别的节点）。"""
    return ctx.screen.click((x, y), delay=延时, desc=desc)


def _等(ctx: TaskContext, 毫秒: int) -> bool:
    """旧节点 ``time_sleep`` / ``time_sleep_1``：纯等待，永远算命中。"""
    ctx.screen.sleep(毫秒)
    return True


def _等到(ctx: TaskContext, 候选: Cand, *, 冻结: Optional[int] = None) -> bool:
    """旧 ``action: DoNothing`` 的节点：只等它出现（不点），等到了再按 ``post_wait_freezes`` 等画面静止。"""
    if not ctx.look(候选):
        return False
    if 冻结:
        ctx.screen.wait_freezes(time=冻结)
    return True


def _空(ctx: TaskContext) -> bool:
    """旧节点 ``empty`` / ``sub_choose_boss``：空对象 = 永远命中、什么都不做，用来终结一张 next 表。"""
    return True


def _扫(ctx: TaskContext, *步骤: Step, 超时: int = 20_000, 说明: str = "") -> bool:
    """旧 ``next`` 表：反复试这几个步骤，谁先命中就做谁。"""
    return bool(ctx.scan(*步骤, timeout=超时, desc=说明))


# ======================================================================
# 11_Research.json（13 节点）：入口 → 主题分支 → 地图分支
# ======================================================================


def 点博物入口(ctx: TaskContext) -> bool:
    """旧节点 ``museum``：主界面右下角的「博物」入口。"""
    return _点(
        ctx,
        OCR("博物", roi=(1087, 283, 173, 167), wait_freezes=1000, desc="打开博物研学"),
        前置冻结=500,
    )


def 点研学周常(ctx: TaskContext) -> bool:
    """旧节点 ``Research-week``：点左上角「常奖」页签（``target_offset`` 500,-40）。"""
    return _点(
        ctx,
        OCR("常奖", roi=(0, 75, 400, 180), offset=(500, -40, 0, 0), desc="切到研学页签"),
    )


def 点研学退出(ctx: TaskContext) -> bool:
    """旧节点 ``research_quit``：点右上角返回键退出研学界面（``Research/123.png``）。"""
    return _点(ctx, IMG("Research/123.png", roi=(1200, 25, 60, 70), delay=5000, desc="退出研学"))


def 点研学返回(ctx: TaskContext) -> bool:
    """旧节点 ``research_return``：左上角返回（``Research/115.png``）。"""
    return _点(ctx, IMG("Research/115.png", roi=(0, 0, 264, 100), wait_freezes=500, desc="返回"))


def 点研学返回主页(ctx: TaskContext) -> bool:
    """旧节点 ``research_home``：左上角回主页（``Company/social_back_home.png``）。"""
    return _点(ctx, IMG("Company/social_back_home.png", roi=(0, 0, 300, 100), delay=1000, desc="回主页"))


def 进入博物研学(ctx: TaskContext) -> bool:
    """旧节点 ``museum_Research``：任务入口那张 next 表。"""
    # 旧 next：[museum, research_home, research_return, research_quit,
    #          [JumpBack]Exception-handling-remind, [JumpBack]Exception-handling-nurturance-one]
    return _扫(
        ctx,
        点博物入口,
        点研学返回主页,
        点研学返回,
        点研学退出,
        handle_exceptions,
        超时=60_000,
        说明="进入博物研学",
    )


def 点山水纪行(ctx: TaskContext) -> bool:
    """旧节点 ``mountain-river``：主题列表里的「山水纪行」。"""
    return _点(ctx, IMG("Research/mountain_research.png", roi=(13, 98, 249, 123), desc="选山水纪行"), 前置冻结=500)


def 点金银纪行(ctx: TaskContext) -> bool:
    """旧节点 ``gold-silver``：主题列表里的「金银纪行」。"""
    return _点(ctx, IMG("Research2/golden_research.png", roi=(12, 253, 253, 128), desc="选金银纪行"), 前置冻结=500)


def 点主题确认_山水(ctx: TaskContext) -> bool:
    """旧节点 ``enter_theme_1``：山水纪行的「主题」确认。"""
    return _点(ctx, OCR("主题", roi=(830, 570, 450, 150), wait_freezes=500, desc="确认山水纪行"))


def 点主题确认_金银(ctx: TaskContext) -> bool:
    """旧节点 ``enter_theme_2``：金银纪行的「主题」确认。"""
    return _点(ctx, OCR("主题", roi=(830, 570, 450, 150), wait_freezes=500, desc="确认金银纪行"))


def 点启程(ctx: TaskContext) -> bool:
    """旧节点 ``mountain_Research``：点「启程」进地图（它的 next 被地图选项覆盖，见 :func:`按地图分流`）。"""
    return _点(ctx, OCR("启程", roi=(600, 350, 675, 370), wait_freezes=5000, desc="启程"))


def 点继续研学(ctx: TaskContext) -> bool:
    """旧节点 ``mountain_Research_2``：一局结束后的「继续」。"""
    return _点(ctx, OCR("继续", roi=(600, 350, 675, 370), wait_freezes=2000, desc="继续研学"))


def 选择研学主题(ctx: TaskContext) -> bool:
    """旧节点 ``choose_theme``：旧实现是个「没有识别、只等着被 option 覆盖 next」的占位节点。

    Python 里不需要绕圈了 —— 直接读选项值，查表选分支函数。
    """
    主题名 = ctx.text(主题选项.key, 主题_山水纪行)
    ctx.step(f"研学主题：{主题名}")
    if 主题名 == 主题_金银纪行:
        return 走金银纪行(ctx)
    return 走山水纪行(ctx)


def 走山水纪行(ctx: TaskContext) -> bool:
    """旧节点链 ``mountain-river`` → ``enter_theme_1`` → ``mountain_Research``。"""
    if not _扫(ctx, 点山水纪行, handle_exceptions, 超时=30_000, 说明="选山水纪行"):
        return False
    # 旧 enter_theme_1.next = [mountain_Research, mountain_Research_2, enter_theme_1]
    if not _扫(
        ctx,
        点启程,
        点继续研学,
        点主题确认_山水,
        handle_exceptions,
        超时=60_000,
        说明="进入山水纪行地图",
    ):
        return False
    return 按地图分流(ctx)


def 走金银纪行(ctx: TaskContext) -> bool:
    """旧节点链 ``gold-silver`` → ``enter_theme_2`` → ``gold_research``（是否手动选人的分支）。"""
    if not _扫(ctx, 点金银纪行, handle_exceptions, 超时=30_000, 说明="选金银纪行"):
        return False
    # 旧 enter_theme_2.next = [gold_research, jixu-research, enter_theme_2]
    if not _扫(
        ctx,
        点开始研学,
        点继续研学,
        点主题确认_金银,
        handle_exceptions,
        超时=60_000,
        说明="进入金银纪行",
    ):
        return False
    # 旧节点 gold_research.next 被「是否手动选择角色和buff」覆盖：
    #   手动 → [action_1, jixu-research]；自动 → [choose_boss, sub_choose_boss, action_1]
    if ctx.text(手动选项.key, 手动_自己选) == 手动_自动:
        # 旧 [choose_boss, sub_choose_boss, action_1]：sub_choose_boss 是空节点（永远命中的兜底）
        if not 自动选角色(ctx):
            return False
    else:
        # 手动时旧配置要求「选完角色和 buff、进了博学地图才开始跑」，所以这里等的是营地或「继续」
        if not _扫(ctx, 点营地一, 点继续研学, handle_exceptions, 超时=180_000, 说明="等手动选完角色和 buff"):
            return False
    return 走金银研学(ctx)


def 滑动角色列表(ctx: TaskContext) -> bool:
    """旧节点 ``swipe_page``：角色列表拖一页（780,362 → 475,362，1 秒，停 0.5 秒）。"""
    ctx.screen.swipe((780, 362), (475, 362), duration=1000, delay=500, desc="拖动角色列表")
    return True


def 找商鞅方升(ctx: TaskContext) -> bool:
    """旧节点 ``find_shangyang``：在角色列表里点「商鞅方升」。"""
    return _点(ctx, OCR("商鞅方升", desc="选商鞅方升"))


def 自动选角色(ctx: TaskContext) -> bool:
    """旧节点链 ``choose_boss`` → ``choose_role`` → ``change_filter`` → ``choose_tag`` →
    ``ensure_tag`` → ``swipe_page``/``find_shangyang`` → ``change_tag`` → ``choose_tag_2`` →
    ``ensure_tag_1`` → ``choose_role_1``/``_2``/``_3`` → ``ensure_1`` → ``choose_strategy`` →
    ``start_research``：由 MWA 自动挑角色 / 辅助效果。"""
    if not 点选首领_骨刻(ctx):
        return False
    if not 点选角色(ctx):
        return False
    if not 点筛选(ctx):
        return False
    if not 点轻锐标签(ctx):
        return False
    if not 点筛选确定(ctx):
        return False
    # 旧 ensure_tag.next = [find_shangyang, [JumpBack]swipe_page]：找到就点，找不到就拖列表
    if not _扫(ctx, 找商鞅方升, 滑动角色列表, handle_exceptions, 超时=60_000, 说明="找商鞅方升"):
        return False
    if not 点筛选(ctx):
        return False
    if not 点全选标签(ctx):
        return False
    if not 点筛选确定二(ctx):
        return False
    # 旧 ensure_tag_1.next = [choose_role_1] → choose_role_2 → choose_role_3 → ensure_1
    if not 点角色一(ctx):
        return False
    if not 点角色二(ctx):
        return False
    if not 点角色三(ctx):
        return False
    if not 点角色确定(ctx):
        return False
    # 旧 ensure_1.next = [choose_strategy] → start_research
    if not 点辅助效果(ctx):
        return False
    return 点进入研学(ctx)


def 按地图分流(ctx: TaskContext) -> bool:
    """旧节点 ``mountain_Research``：它的 next 被「选择地图(仅老研学)」覆盖成单张地图。

    旧 pipeline 的写法是 ``next: [snowscape, landscape, journey, advance_one_man, ...]``
    + option 覆盖；这里直接按选项查表选分支函数。
    """
    地图名 = ctx.text(地图选项.key, 地图_雪景寒林图)
    ctx.step(f"研学地图：{地图名}")
    if 地图名 == 地图_千里江山图:
        return 走千里江山图(ctx)
    if 地图名 == 地图_溪山旅行图:
        return 走溪山旅行图(ctx)
    if 地图名 == 地图_打新研学:
        # 旧 override 把 next 换成 [] —— 什么都不做，直接把控制权交回上层（等玩家打完再跑）
        ctx.step("打新研学：不自动推进")
        return True
    return 走雪景寒林图(ctx)


# ======================================================================
# 11_(03)_landscape.json / 11_(04)_journey.json：另外两张地图
# ======================================================================


def 点千里江山图(ctx: TaskContext) -> bool:
    """旧节点 ``landscape``：地图上的千里江山图（``Research/r1.png``）。"""
    return _点(ctx, IMG("Research/r1.png", roi=(494, 386, 90, 84), offset=(60, 150, 0, 0), wait_freezes=3000, desc="点千里江山图"))


def 点千里江山图buff(ctx: TaskContext) -> bool:
    """旧节点 ``landscape-buff-one``：点「选择初始 buff」（无识别，DirectHit 点 360,340）。"""
    return _点坐标(ctx, 360, 340, 延时=3000, desc="选初始 buff（千里江山图）")


def 点溪山旅行图(ctx: TaskContext) -> bool:
    """旧节点 ``journey``：地图上的溪山旅行图（``Research/r2.png``）。"""
    return _点(ctx, IMG("Research/r2.png", roi=(878, 385, 92, 90), offset=(60, 150, 0, 0), wait_freezes=3000, desc="点溪山旅行图"))


def 点溪山旅行图buff(ctx: TaskContext) -> bool:
    """旧节点 ``journey-buff-one``：点「选择初始 buff」（无识别，DirectHit 点 360,340）。"""
    return _点坐标(ctx, 360, 340, 延时=3000, desc="选初始 buff（溪山旅行图）")


def 走千里江山图(ctx: TaskContext) -> bool:
    """旧节点链 ``landscape`` → ``landscape-buff-one`` → 技能 → ``agree`` → 地图推进。"""
    if not _扫(
        ctx,
        点千里江山图,
        点千里江山图buff,
        点神射,
        点炽刀,
        点术法精通,
        点同意,
        点新状态,
        handle_exceptions,
        超时=180_000,
        说明="进入千里江山图",
    ):
        return False
    return 推进研学地图(ctx, 地图表)


def 走溪山旅行图(ctx: TaskContext) -> bool:
    """旧节点链 ``journey`` → ``journey-buff-one`` → 技能 → ``agree`` → 地图推进。"""
    if not _扫(
        ctx,
        点溪山旅行图,
        点溪山旅行图buff,
        点神射,
        点炽刀,
        点术法精通,
        点同意,
        点新状态,
        handle_exceptions,
        超时=180_000,
        说明="进入溪山旅行图",
    ):
        return False
    return 推进研学地图(ctx, 地图表)


# ======================================================================
# 11_2_goldresearch.json（62 节点）：金银纪行
# ======================================================================


def 点开始研学(ctx: TaskContext) -> bool:
    """旧节点 ``gold_research``：点「开始研学」（``Research2/begin_research.png``）。"""
    return _点(ctx, IMG("Research2/begin_research.png", roi=(830, 570, 450, 150), desc="开始研学"), 前置冻结=500)


def 点选首领_骨刻(ctx: TaskContext) -> bool:
    """旧节点 ``choose_boss``：选默认首领「骨刻」。"""
    return _点(ctx, OCR("骨刻", roi=(165, 493, 974, 41), desc="选首领骨刻"), 前置冻结=500)


def 点选角色(ctx: TaskContext) -> bool:
    """旧节点 ``choose_role``：点「选择角色」（``Research2/choose_role.png``）。"""
    return _点(ctx, IMG("Research2/choose_role.png", desc="选择角色"), 前置冻结=500)


def 点筛选(ctx: TaskContext) -> bool:
    """旧节点 ``change_filter`` / ``change_tag``：右上角筛选按钮（``Research2/filter.png``）。"""
    return _点(ctx, IMG("Research2/filter.png", roi=(1197, 10, 61, 42), desc="打开筛选"))


def 点轻锐标签(ctx: TaskContext) -> bool:
    """旧节点 ``choose_tag``：筛选面板里选「轻锐」。"""
    return _点(ctx, OCR("轻锐", roi=(469, 207, 501, 60), desc="选轻锐"))


def 点筛选确定(ctx: TaskContext) -> bool:
    """旧节点 ``ensure_tag``：筛选面板的「确定」。"""
    return _点(ctx, OCR("确定", desc="确定筛选"))


def 点全选标签(ctx: TaskContext) -> bool:
    """旧节点 ``choose_tag_2``：筛选面板里切回「全部」。"""
    return _点(ctx, OCR("全部", roi=(469, 207, 501, 60), desc="切回全部"))


def 点筛选确定二(ctx: TaskContext) -> bool:
    """旧节点 ``ensure_tag_1``：第二次筛选的「确定」。"""
    return _点(ctx, OCR("确定", desc="确定筛选（二）"))


def 点角色一(ctx: TaskContext) -> bool:
    """旧节点 ``choose_role_1``：DirectHit 点第一个角色的位置（554,511）。"""
    return _点坐标(ctx, 554, 511, desc="选角色一")


def 点角色二(ctx: TaskContext) -> bool:
    """旧节点 ``choose_role_2``：DirectHit 点第二个角色的位置（693,191）。"""
    return _点坐标(ctx, 693, 191, desc="选角色二")


def 点角色三(ctx: TaskContext) -> bool:
    """旧节点 ``choose_role_3``：DirectHit 点第三个角色的位置（699,516）。"""
    return _点坐标(ctx, 699, 516, desc="选角色三")


def 点角色确定(ctx: TaskContext) -> bool:
    """旧节点 ``ensure_1``：选角色面板右下角的确定（``Research2/ensure_1.png``）。"""
    return _点(ctx, IMG("Research2/ensure_1.png", roi=(1167, 672, 54, 36), desc="确定选人"))


def 点辅助效果(ctx: TaskContext) -> bool:
    """旧节点 ``choose_strategy``：点「辅助效果」。"""
    return _点(ctx, OCR("辅助效果", desc="选辅助效果"))


def 点进入研学(ctx: TaskContext) -> bool:
    """旧节点 ``start_research``：点「进入研学」。"""
    return _点(ctx, OCR("进入研学", delay=2000, desc="进入研学"))


def 等研学加载完成(ctx: TaskContext) -> bool:
    """旧节点 ``loading_wait``：``inverse`` 模板匹配 —— 画面里**看不到** ``Research2/start_point.png``
    才算进图完成（旧的 ``[JumpBack]loading_wait`` 就是靠 inverse 当等待条件用的）。"""
    return ctx.wait_for(lambda: ctx.screen.find("Research2/start_point.png") is None, timeout=90_000)


def 处理营地结算(ctx: TaskContext) -> bool:
    """旧节点 ``ensure_2`` → ``ensure_3``：营地行动后的「休息」结算和「确认」。"""
    if not _点(ctx, OCR("休息", roi=(991, 493, 114, 46), desc="点休息"), 前置冻结=700):
        return False
    # 旧 next：[ensure_3, [JumpBack]ensure_2] —— 可能连续弹几次结算，这里循环而不是递归
    for _ in range(5):
        if _点(ctx, OCR("确认", roi=(839, 619, 116, 50), desc="确认结算"), 前置冻结=300):
            return True
        if not _点(ctx, OCR("休息", roi=(991, 493, 114, 46), desc="再点休息"), 前置冻结=700):
            return True
    return True


def 点营地一(ctx: TaskContext) -> bool:
    """旧节点 ``action_1``：营地（休息图标索引 0）→ ``[JumpBack]ensure_2`` → ``action_2``。"""
    if not _点图索引(ctx, "Research2/rest.png", 索引=0, 绿幕=True, 前置冻结=1000, 后置冻结=500, desc="营地 1"):
        return False
    return _扫(ctx, 处理营地结算, 点营地二, 超时=30_000, 说明="营地 1 之后")


def 点营地二(ctx: TaskContext) -> bool:
    """旧节点 ``action_2``：营地（休息图标索引 2）→ ``ensure_2`` → ``action_3``。"""
    if not _点图索引(ctx, "Research2/rest.png", 索引=2, 绿幕=True, 后置冻结=500, desc="营地 2"):
        return False
    return _扫(ctx, 处理营地结算, 点战斗位一, 超时=30_000, 说明="营地 2 之后")


def 点地图返回(ctx: TaskContext) -> bool:
    """旧节点 ``swipe_map`` / ``swipe_map_2``：点左上角返回键回地图（``Research/115.png``）。"""
    return _点图索引(ctx, "Research/115.png", roi=(0, 0, 264, 100), 前置冻结=500, 后置冻结=500, desc="返回地图")


def 点战斗位一(ctx: TaskContext) -> bool:
    """旧节点 ``action_3``：地图上索引 1 的战斗点 → ``fight`` → ``swipe_map``。"""
    if not _点图索引(ctx, "Research2/fight.png", 索引=1, 绿幕=True, 后置冻结=500, desc="打第一个战斗点"):
        return False
    if not _扫(ctx, 打金银战斗, 超时=120_000, 说明="战斗 1 之后"):
        return False
    # 旧 action_3.next = [[JumpBack]fight, swipe_map]；swipe_map.next = [enter_research] → action_4
    if not 点地图返回(ctx):
        return False
    if not 点继续进研学(ctx):
        return False
    return 点营地四(ctx)


def 点继续进研学(ctx: TaskContext) -> bool:
    """旧节点 ``enter_research`` / ``enter_research_2``：地图上的「继续」。"""
    return _点(ctx, IMG("Research2/continue.png", roi=(891, 611, 377, 100), desc="继续进图"))


def 点营地四(ctx: TaskContext) -> bool:
    """旧节点 ``action_4``：营地（索引 0，roi 166,2,917,717）→ ``ensure_2`` → ``action_5``。"""
    if not _点图索引(ctx, "Research2/rest.png", 索引=0, 绿幕=True, roi=(166, 2, 917, 717), 后置冻结=500, desc="营地 4"):
        return False
    return _扫(ctx, 处理营地结算, 点战斗位二, 超时=30_000, 说明="营地 4 之后")


def 点战斗位二(ctx: TaskContext) -> bool:
    """旧节点 ``action_5``：索引 2 的战斗点（``Research2\\fight.png``）→ ``fight`` → ``action_6``。"""
    if not _点图索引(ctx, "Research2/fight.png", 索引=2, 绿幕=True, 后置冻结=500, desc="打第二个战斗点"):
        return False
    return _扫(ctx, 打金银战斗, 点战斗位三, 超时=120_000, 说明="战斗之后")


def 点战斗位三(ctx: TaskContext) -> bool:
    """旧节点 ``action_6``：``Research2\\fight_2.png``（索引 0）→ ``fight`` → ``swipe_map_2``。"""
    if not _点图索引(ctx, "Research2/fight_2.png", 索引=0, 绿幕=True, 后置冻结=500, desc="打第三个战斗点"):
        return False
    if not _扫(ctx, 打金银战斗, 超时=120_000, 说明="战斗 3 之后"):
        return False
    # 旧 action_6.next = [[JumpBack]fight, swipe_map_2]；swipe_map_2 → enter_research_2 → action_7
    if not 点地图返回(ctx):
        return False
    if not 点继续进研学(ctx):
        return False
    return 点添加角色一(ctx)


def 点添加角色一(ctx: TaskContext) -> bool:
    """旧节点 ``action_7``：``add_people.png``（索引 0）→ ``[JumpBack]import_1`` → ``action_8``。

    ``action_10`` 与它同构（后面接 ``action_11``）。
    """
    if not _点图索引(ctx, "Research2/add_people.png", 索引=0, 绿幕=True, 后置冻结=500, desc="添加人手 1"):
        return False
    return _扫(ctx, 导入角色, 点战斗位四, 超时=60_000, 说明="导入人手之后")


def 点战斗位四(ctx: TaskContext) -> bool:
    """旧节点 ``action_8``：``fight.png``（索引 1）→ ``fight`` → ``action_9``。"""
    if not _点图索引(ctx, "Research2/fight.png", 索引=1, 绿幕=True, 后置冻结=500, desc="打第四个战斗点"):
        return False
    return _扫(ctx, 打金银战斗, 打第五个战斗点, 超时=120_000, 说明="战斗之后")


def 打第五个战斗点(ctx: TaskContext) -> bool:
    """旧节点 ``action_9``：``fight_2.png``（索引 1）→ ``fight`` → ``swipe_map_3``。"""
    if not _点图索引(ctx, "Research2/fight_2.png", 索引=1, 绿幕=True, 后置冻结=500, desc="打第五个战斗点"):
        return False
    # 旧 swipe_map_3：一场 Swipe，把地图拖回来
    ctx.screen.swipe((934, 153), (540, 150), duration=300, desc="拖动地图")
    return 点添加角色二(ctx)


def 点添加角色二(ctx: TaskContext) -> bool:
    """旧节点 ``action_10``：``add_people.png``（索引 0）→ ``[JumpBack]import_1`` → ``action_11``。"""
    if not _点图索引(ctx, "Research2/add_people.png", 索引=0, 绿幕=True, 后置冻结=500, desc="添加人手 2"):
        return False
    return _扫(ctx, 导入角色, 点营地十一, 超时=60_000, 说明="导入人手之后")


def 点营地十一(ctx: TaskContext) -> bool:
    """旧节点 ``action_11``：``rest.png``/``rest2.png`` 两张图纵排取索引 1 → ``ensure_2`` → ``action_12``。"""
    if not _点图索引(
        ctx,
        ["Research2/rest.png", "Research2/rest2.png"],
        排序="Vertical",
        索引=1,
        绿幕=True,
        后置冻结=500,
        desc="营地 11",
    ):
        return False
    return _扫(ctx, 处理营地结算, 点首领挑战, 超时=30_000, 说明="营地 11 之后")


def 点首领挑战(ctx: TaskContext) -> bool:
    """旧节点 ``action_12``：``boss.png`` → ``[JumpBack]fight`` → ``finish_research``。"""
    if not _点图索引(ctx, "Research2/boss.png", 绿幕=True, 后置冻结=500, desc="挑战首领"):
        return False
    if not _扫(ctx, 打金银战斗, 超时=120_000, 说明="首领战斗"):
        return False
    return 结束金银研学(ctx)


def 导入角色(ctx: TaskContext) -> bool:
    """旧节点 ``import_1``：点「导入」→ ``immport_2`` → ``choose_first`` → ``ensure_7`` → ``ensure_8``。"""
    if not _点(ctx, OCR("导入", roi=(993, 489, 108, 54), wait_freezes=300, desc="导入")):
        return False
    if not _点(ctx, IMG("Research2/import.png", wait_freezes=500, desc="确认导入")):
        return False
    if not _点坐标(ctx, 550, 190, desc="选第一个（旧节点 choose_first）"):
        return False
    if not _点(ctx, IMG("Research2/ensure_1.png", roi=(1167, 672, 54, 36), wait_freezes=500, desc="勾选")):
        return False
    return _点(ctx, OCR("确认", roi=(971, 537, 122, 56), wait_freezes=500, desc="确认导入"))


def 打金银战斗(ctx: TaskContext) -> bool:
    """旧节点 ``fight`` → ``fight_begin`` → ``not_full``/``auto``/``fight_begin2`` → ``ensure_4``
    → ``choose_buff``/``regular_buff``/``random_buff``/``ensure_5``/``new_buff``/``ensure_6``。"""
    if not _点(ctx, OCR("战斗", roi=(858, 474, 389, 80), wait_freezes=500, desc="进入战斗")):
        return False
    if not _点(ctx, OCR("开始", roi=(1030, 617, 200, 74), desc="开始战斗")):
        return False
    # 旧 fight_begin.next = [not_full, auto, fight_begin2, [JumpBack]time_sleep_1]
    if not _扫(
        ctx,
        点角色未满,
        点自动战斗,
        点开始战斗确认,
        handle_exceptions,
        超时=30_000,
        说明="准备战斗",
    ):
        return False
    # 旧 fight_begin2.next = [ensure_4, [JumpBack]time_sleep]（time_sleep = 等 2 秒）
    if not _扫(ctx, 点战斗确定, _等两秒, handle_exceptions, 超时=60_000, 说明="点确定"):  # ensure_4
        return False
    # 旧 ensure_4.next = [choose_buff, quit_research_2]
    if not _扫(ctx, 选战斗buff, 结束金银研学, handle_exceptions, 超时=60_000, 说明="战斗结算"):
        return False
    return True


def 点角色未满(ctx: TaskContext) -> bool:
    """旧节点 ``not_full``：提示「角色未满」的确认（``Research2\\ensure_2.png``）。"""
    return _点图索引(ctx, "Research2/ensure_2.png", roi=(686, 396, 169, 62), 前置延时=500, desc="角色未满提示")


def 点自动战斗(ctx: TaskContext) -> bool:
    """旧节点 ``auto``：右上角自动战斗开关（``Research2\\auto.png``）。"""
    return _点图索引(ctx, "Research2/auto.png", roi=(1196, 123, 78, 67), 后置冻结=500, desc="开自动")


def 点开始战斗确认(ctx: TaskContext) -> bool:
    """旧节点 ``fight_begin2``：开始战斗（``Research2\\begin_fight.png``）。"""
    return _点图索引(ctx, "Research2/begin_fight.png", roi=(1012, 621, 268, 99), desc="开始战斗")


def 点战斗确定(ctx: TaskContext) -> bool:
    """旧节点 ``ensure_4``：战斗结算的「确定」。"""
    return _点(ctx, OCR("确定", roi=(913, 626, 125, 53), wait_freezes=500, desc="结算确定"), 前置冻结=1000)


def _等两秒(ctx: TaskContext) -> bool:
    """旧节点 ``time_sleep``：等 2 秒（``time_sleep_1`` 是 0.5 秒，见 :func:`_等五百毫秒`）。"""
    return _等(ctx, 2000)


def _等五百毫秒(ctx: TaskContext) -> bool:
    """旧节点 ``time_sleep_1``：等 0.5 秒。"""
    return _等(ctx, 500)


def 选战斗buff(ctx: TaskContext) -> bool:
    """旧节点 ``choose_buff`` → ``regular_buff``/``random_buff`` → ``ensure_5`` → ``new_buff``/``ensure_6``。"""
    # choose_buff：DoNothing，只是等 buff 面板出来
    if not ctx.wait_for(lambda: ctx.look(IMG("Research2/buff.png", desc="buff 面板")), timeout=30_000):
        return False
    for _ in range(6):
        if not _点(ctx, OCR("破军", roi=(210, 327, 860, 37), delay=0, desc="选破军")):
            # 旧节点 random_buff：没有「破军」就直接点第一个随机 buff（DirectHit 335,370）
            _点坐标(ctx, 335, 370, desc="随机 buff")
        # 旧节点 ensure_5 / ensure_6：确认
        if _点(ctx, OCR("确认", roi=(768, 610, 253, 62), desc="buff 确认"), 前置冻结=500):
            ctx.screen.sleep(1000)
        if not ctx.screen.find("Research2/buff.png"):
            break
    return True


def 结束金银研学(ctx: TaskContext) -> bool:
    """旧节点 ``quit_research_2`` → ``ensure_quit`` → ``finish_research``：收尾退出研学。"""
    if not _点(ctx, IMG("Research2/quit.png", wait_freezes=500, desc="退出研学")):
        return False
    if not _点(ctx, IMG("Research2/ensure_1.png", desc="确认退出")):
        return False
    if not _点(ctx, OCR("结束", roi=(1021, 565, 246, 88), desc="结束研学"), 前置冻结=500):
        return False
    return True


def 走金银研学(ctx: TaskContext) -> bool:
    """旧节点链 ``action_1`` → ``action_2`` → … → ``action_12``（金色研学的营地推进）。

    旧图里每个 ``action_*`` 的 next 都是 ``[JumpBack]ensure_2``/``[JumpBack]fight`` 加下一个
    ``action_*``；这里按顺序写下来，中间那两种「跳回来」用 :func:`_扫` 表达。
    """
    # 旧 gold_research.next 里的 ``[JumpBack]loading_wait``：inverse 匹配，等进图完成
    if not 等研学加载完成(ctx):
        return False
    # 旧节点 action_1 是这条链的起点，后面的 action_2 … action_12 由它一路接下去
    return _扫(ctx, 点营地一, handle_exceptions, 超时=90_000, 说明="营地 1（旧节点 action_1）")


# ------------------------------------------------------------------ 地图推进
#
# 11_(02)_snowscape.json 里 ``advance_two`` / ``advance_three`` / ``advance_four`` 这三张
# next 表互相包含，而且每个事件节点命中之后又会回到同样的表 —— 逐节点照抄会无限递归。
# 这里并成一张 :data:`地图表`，用 :func:`推进研学地图` 的 while 循环反复扫。


def 点雪景寒林图(ctx: TaskContext) -> bool:
    """旧节点 ``snowscape``：地图上的雪景寒林图（``Research/82.png``，点图标右下偏一点）。"""
    return _点(
        ctx,
        IMG("Research/82.png", roi=(109, 384, 80, 86), offset=(70, 130, 0, 0), delay=3000, desc="点雪景寒林图"),
    )


def 点初始buff(ctx: TaskContext) -> bool:
    """旧节点 ``buff-one``：点（360,340）这个「选择初始 buff」的按钮（无识别，DirectHit）。"""
    return _点坐标(ctx, 360, 340, 延时=3000, desc="选初始 buff")


def 点神射(ctx: TaskContext) -> bool:
    """旧节点 ``Marksmanship``：初始 buff「神射」。"""
    return _点(ctx, OCR("神射", roi=(210, 258, 830, 110), wait_freezes=2000, desc="选神射"))


def 点炽刀(ctx: TaskContext) -> bool:
    """旧节点 ``Blazing_Knife``：初始 buff「炽刀」。"""
    return _点(ctx, OCR("炽刀", roi=(210, 258, 830, 110), wait_freezes=2000, desc="选炽刀"))


def 点术法精通(ctx: TaskContext) -> bool:
    """旧节点 ``Spells``：初始 buff「术法精通」。"""
    return _点(ctx, OCR("术法精通", roi=(210, 258, 830, 110), wait_freezes=2000, desc="选术法精通"))


def 点同意(ctx: TaskContext) -> bool:
    """旧节点 ``agree``：点「同意」（``Research/83.png``）。"""
    return _点(ctx, IMG("Research/83.png", roi=(508, 604, 268, 79), delay=4000, desc="同意"))


def 点新状态(ctx: TaskContext) -> bool:
    """旧节点 ``new_state``：点状态提示（``Research/58.png``）。"""
    return _点(ctx, IMG("Research/58.png", roi=(485, 23, 312, 108), delay=2000, desc="新状态"))


def 点前进一_男(ctx: TaskContext) -> bool:
    """旧节点 ``advance_one_man``：男主（``Research/84.png``）往前走一格。"""
    return _点图索引(
        ctx, "Research/84.png", roi=角色区, 阈值=0.6, 绿幕=True, 偏移=(190, 0, 0, 0), 延时=3000, desc="男主前进 1"
    )


def 点前进一_女(ctx: TaskContext) -> bool:
    """旧节点 ``advance_one_women``：女主（``Research/85.png``）往前走一格。"""
    return _点图索引(
        ctx, "Research/85.png", roi=角色区, 阈值=0.6, 绿幕=True, 偏移=(190, 0, 0, 0), 延时=3000, desc="女主前进 1"
    )


def 点不可以往这里(ctx: TaskContext) -> bool:
    """旧节点 ``no_click``：弹出「不可以往这里」（说明这位角色走不动了）。"""
    return _点(ctx, OCR("不可以往这里", desc="这位走不动"))


def 点前往(ctx: TaskContext) -> bool:
    """旧节点 ``advance_two``：点「前往」（``post_delay`` 5 秒）。

    ``advance_three`` 的识别完全一样、只是 ``post_delay`` 是 2 秒，这里合成一步，
    在报告里单独标出。
    """
    return _点(ctx, OCR("前往", delay=5000, desc="前往"))


def _造前进(节点名: str, 图: str, 偏移: tuple[int, int, int, int], 说明: str):
    """给 ``advance_two_*`` … ``advance_nine_*`` 这 16 个同构节点造函数。

    它们的差别只有「男图/女图」和 ``target_offset``；旧图里点完之后会去 ``fixed_*``
    那几个纯 next 节点，而 ``fixed_*`` 的内容（前进按钮 + 前往）本来就在 :data:`地图表` 里。
    """

    def 前进(ctx: TaskContext) -> bool:
        return _点图索引(
            ctx, 图, roi=角色区, 阈值=0.6, 绿幕=True, 偏移=偏移, 延时=3000, desc=说明
        )

    前进.__name__ = 节点名
    前进.__doc__ = f"旧节点 ``{节点名}``：{说明}。"
    return 前进


点前进二_男 = _造前进("advance_two_man", "Research/84.png", (260, -15, 0, 0), "男主前进 2")
点前进二_女 = _造前进("advance_two_women", "Research/85.png", (260, -15, 0, 0), "女主前进 2")
点前进三_男 = _造前进("advance_three_man", "Research/84.png", (100, -130, 0, 0), "男主前进 3")
点前进三_女 = _造前进("advance_three_women", "Research/85.png", (100, -130, 0, 0), "女主前进 3")
点前进四_男 = _造前进("advance_four_man", "Research/84.png", (310, 100, 0, 0), "男主前进 4")
点前进四_女 = _造前进("advance_four_women", "Research/85.png", (310, 100, 0, 0), "女主前进 4")
点前进五_男 = _造前进("advance_five_man", "Research/84.png", (240, -40, 0, 0), "男主前进 5")
点前进五_女 = _造前进("advance_five_women", "Research/85.png", (240, -40, 0, 0), "女主前进 5")
点前进六_男 = _造前进("advance_six_man", "Research/84.png", (240, 15, 0, 0), "男主前进 6")
点前进六_女 = _造前进("advance_six_women", "Research/85.png", (240, 15, 0, 0), "女主前进 6")
点前进七_男 = _造前进("advance_seven_man", "Research/84.png", (320, 20, 0, 0), "男主前进 7")
点前进七_女 = _造前进("advance_seven_women", "Research/85.png", (320, 20, 0, 0), "女主前进 7")
点前进八_男 = _造前进("advance_eight_man", "Research/84.png", (280, 0, 0, 0), "男主前进 8")
点前进八_女 = _造前进("advance_eight_women", "Research/85.png", (280, 0, 0, 0), "女主前进 8")
点前进九_男 = _造前进("advance_nine_man", "Research/84.png", (200, -30, 0, 0), "男主前进 9")
点前进九_女 = _造前进("advance_nine_women", "Research/85.png", (200, -30, 0, 0), "女主前进 9")

#: 旧节点 ``fixed_one`` … ``fixed_nine``：没有识别、只有 next 的纯跳转节点。
#: 它们的内容（下一组前进按钮 + 前往）都已经在 :data:`地图表` 里，这里只留一份对照表。
固定位后续 = {
    "fixed_one": ("advance_one_man", "advance_one_women", "advance_four"),
    "fixed_two": ("advance_two_man", "advance_two_women", "advance_four"),
    "fixed_three": ("advance_three_man", "advance_three_women", "advance_four"),
    "fixed_four": ("advance_four_man", "advance_four_women", "advance_four"),
    "fixed_five": ("advance_five_man", "advance_five_women", "advance_four"),
    "fixed_six": ("advance_six_man", "advance_six_women", "advance_four"),
    "fixed_seven": ("advance_seven_man", "advance_seven_women", "advance_four"),
    "fixed_eight": ("advance_eight_man", "advance_eight_women", "advance_four"),
    "fixed_nine": ("advance_nine_man", "advance_nine_women", "advance_four"),
}


# ------------------------------------------------------- 雪景寒林图的随机事件
#
# 每个事件都是「点标题（识别）→ 点选项」两步。标题是模板还是 OCR 照抄旧节点；
# 选项若旧节点用的是 OCR，就走 :func:`选事件选项` 查 event.json 那张表。


def 点迷雾(ctx: TaskContext) -> bool:
    """旧节点 ``mist``：事件「寒雾」的标题（``Research/11.png``）。"""
    return _点(ctx, IMG("Research/11.png", roi=事件标题区, wait_freezes=2000, desc="事件：寒雾"))


def 点迷雾选项(ctx: TaskContext) -> bool:
    """旧节点 ``mist_2``：寒雾的选项（``Research/12.png``）。"""
    return _点(ctx, IMG("Research/12.png", roi=事件选项区, wait_freezes=2000, desc="寒雾：选选项"))


def 点风雪之途(ctx: TaskContext) -> bool:
    """旧节点 ``Snow``：事件「风雪之途」的标题。"""
    return _点(ctx, OCR("风雪之途", roi=事件标题区, wait_freezes=2000, desc="事件：风雪之途"))


def 点风雪之途选项(ctx: TaskContext) -> bool:
    """旧节点 ``snow_2``：风雪之途的选项（``Research/22.png``）。"""
    return _点(ctx, IMG("Research/22.png", roi=事件选项区, wait_freezes=2000, desc="风雪之途：选选项"))


def 点山雪之约(ctx: TaskContext) -> bool:
    """旧节点 ``mountain_snow``：事件「山雪之约」的标题（``Research/42.png``）。"""
    return _点(ctx, IMG("Research/42.png", roi=事件标题区, wait_freezes=2000, desc="事件：山雪之约"))


def 点山雪之约选项(ctx: TaskContext) -> bool:
    """旧节点 ``mountain_snow_2``：山雪之约的选项（``Research/43.png``）。"""
    return _点(ctx, IMG("Research/43.png", roi=事件选项区, wait_freezes=2000, desc="山雪之约：选选项"))


def 点巡雪山(ctx: TaskContext) -> bool:
    """旧节点 ``patrol_the_mountains``：事件「巡山雪」的标题。"""
    return _点(ctx, OCR("巡雪山", roi=事件标题区, wait_freezes=2000, desc="事件：巡山雪"))


def 点巡雪山选项(ctx: TaskContext) -> bool:
    """旧节点 ``patrol_the_mountains_2``：巡山雪的选项「到路途中去。」（查 :data:`事件选项`）。"""
    return 选事件选项(ctx, "巡山雪")


def 点再遇寒雪(ctx: TaskContext) -> bool:
    """旧节点 ``cold_snow``：事件「再遇寒雪」的标题。"""
    return _点(ctx, OCR("再遇寒雪", roi=事件标题区, wait_freezes=2000, desc="事件：再遇寒雪"))


def 点再遇寒雪选项(ctx: TaskContext) -> bool:
    """旧节点 ``cold_snow_2``：再遇寒雪的选项「顺势聊起山水画的事情。」（查 :data:`事件选项`）。"""
    return 选事件选项(ctx, "再遇寒雪")


def 点日出东山(ctx: TaskContext) -> bool:
    """旧节点 ``sunrise``：事件「日出东山」的标题（``Research/62.png``）。"""
    return _点(ctx, IMG("Research/62.png", roi=事件标题区, wait_freezes=2000, desc="事件：日出东山"))


def 点日出东山选项(ctx: TaskContext) -> bool:
    """旧节点 ``sunrise_2``：日出东山的选项（``Research/64.png``）。"""
    return _点(ctx, IMG("Research/64.png", roi=事件选项区, wait_freezes=2000, desc="日出东山：选选项"))


def 点小心脚下(ctx: TaskContext) -> bool:
    """旧节点 ``underfoot``：事件「小心脚下」的标题（``Research/88.png``）。"""
    return _点(ctx, IMG("Research/88.png", roi=事件标题区, wait_freezes=2000, desc="事件：小心脚下"))


def 点小心脚下选项(ctx: TaskContext) -> bool:
    """旧节点 ``underfoot_2``：小心脚下的选项「拿起来仔细观察」（查 :data:`事件选项`）。"""
    return 选事件选项(ctx, "小心脚下")


def 点线路规划(ctx: TaskContext) -> bool:
    """旧节点 ``planning``：事件「线路规划」的标题。"""
    return _点(ctx, OCR("线路规划", roi=事件标题区, wait_freezes=2000, desc="事件：线路规划"))


def 点线路规划选项(ctx: TaskContext) -> bool:
    """旧节点 ``planning_2``：线路规划的选项（``Research/97.png``）。"""
    return _点(ctx, IMG("Research/97.png", roi=事件选项区, delay=4000, desc="线路规划：选选项"))


def 点杂学之用(ctx: TaskContext) -> bool:
    """旧节点 ``Miscellaneous``：事件「杂学之用」的标题（``Research/120.png``）。"""
    return _点(ctx, IMG("Research/120.png", roi=事件标题区, wait_freezes=2000, desc="事件：杂学之用"))


def 点杂学之用选项(ctx: TaskContext) -> bool:
    """旧节点 ``Miscellaneous_2``：杂学之用的选项（``Research/94.png``）。"""
    return _点(ctx, IMG("Research/94.png", roi=事件选项区, wait_freezes=2000, desc="杂学之用：选选项"))


def 点护林小屋(ctx: TaskContext) -> bool:
    """旧节点 ``ranger``：事件「护林小屋」的标题。"""
    return _点(ctx, OCR("护林小屋", roi=事件标题区, wait_freezes=2000, desc="事件：护林小屋"))


def 点护林小屋选项(ctx: TaskContext) -> bool:
    """旧节点 ``ranger_2``：护林小屋的选项「询问护林员」（查 :data:`事件选项`）。"""
    return 选事件选项(ctx, "护林小屋")


def 点神秘快递(ctx: TaskContext) -> bool:
    """旧节点 ``mysterious``：事件「神秘快递」的标题。"""
    return _点(ctx, OCR("神秘快递", roi=事件标题区, wait_freezes=2000, desc="事件：神秘快递"))


def 点神秘快递选项(ctx: TaskContext) -> bool:
    """旧节点 ``mysterious_2``：神秘快递的选项「当场打开」/「拆开」（查 :data:`事件选项`）。"""
    return 选事件选项(ctx, "神秘快递")


def 点画性大发(ctx: TaskContext) -> bool:
    """旧节点 ``painting``：事件「画性大发」的标题。"""
    return _点(ctx, OCR("画性", roi=事件标题区, wait_freezes=2000, desc="事件：画性大发"))


def 点画性大发选项(ctx: TaskContext) -> bool:
    """旧节点 ``painting_2``：画性大发的选项（旧节点认的是老包文案「我正好有带」）。"""
    return 选事件选项(ctx, "画性大发")


def 点获得物资(ctx: TaskContext) -> bool:
    """旧节点 ``articles``：事件奖励里的「获得物资」。"""
    return _点(ctx, OCR("获得物资", delay=1500, desc="获得物资"))


# ------------------------------------------------------- 雪景寒林图的进度与升级


def 点宿命(ctx: TaskContext) -> bool:
    """旧节点 ``predestination``：事件结果「命中注定」（``Research/86.png``）。"""
    return _点(ctx, IMG("Research/86.png", roi=事件选项区, delay=2000, desc="命中注定"))


def 点完美(ctx: TaskContext) -> bool:
    """旧节点 ``perfect``：事件结果「完美」（``Research/65.png``）。"""
    return _点(ctx, IMG("Research/65.png", roi=事件选项区, delay=2000, desc="完美"))


def 点继续(ctx: TaskContext) -> bool:
    """旧节点 ``keep``：事件对话的「继续」。"""
    return _点(ctx, OCR("继续", roi=(590, 370, 135, 100), delay=2000, desc="继续对话"))


def 点关键词(ctx: TaskContext) -> bool:
    """旧节点 ``keyword``：事件里的「关键词」（``Research/15.png``）。"""
    return _点(ctx, IMG("Research/15.png", delay=2000, desc="关键词"))


#: 六个升级位的按钮坐标（旧节点 ``upgrade_one`` … ``upgrade_six`` 的 ``target``）。
升级位 = (
    ("upgrade_one", (600, 310)),
    ("upgrade_two", (650, 405)),
    ("upgrade_three", (550, 405)),
    ("upgrade_four", (260, 315)),
    ("upgrade_five", (320, 390)),
    ("upgrade_six", (215, 405)),
)

#: 六个降阶位的按钮坐标（旧节点 ``descending_one`` … ``descending_six`` 的 ``target``，
#: 和升级位一一对应）。
降阶位 = (
    ("descending_one", (600, 310)),
    ("descending_two", (650, 405)),
    ("descending_three", (550, 405)),
    ("descending_four", (260, 315)),
    ("descending_five", (320, 390)),
    ("descending_six", (215, 405)),
)


def 升级装备(ctx: TaskContext) -> bool:
    """旧节点链 ``upgrade_one`` → ``choose`` → ``revise`` → ``upgrade_two`` → ``choose_2``
    → ``revise_2`` → ``upgrade_three`` → ``choose_3`` → ``revise_3`` → ``upgrade_four`` →
    ``choose_4`` → ``revise_4`` → ``upgrade_five`` → ``choose_5`` → ``revise_5`` →
    ``upgrade_six`` → ``choose_6`` → ``revise_6``（六个位的升级/改修）。

    ``choose`` / ``choose_2`` / ``choose_3`` / ``choose_4`` / ``choose_5`` / ``choose_6``
    是同一个确认弹窗（``Research/17.png``，只是点在不同位的坐标上）；
    ``revise`` / ``revise_2`` / ``revise_3`` / ``revise_4`` / ``revise_5`` / ``revise_6``
    是「这位升不动」时的 ``DoNothing`` 分支（``Research/105.png``）。
    """
    for 节点名, 坐标 in 升级位:
        if not _点图索引(
            ctx,
            "Research/16.png",
            roi=升级按钮区,
            后置冻结=2000,
            desc=f"升级菜单位（旧节点 {节点名}）",
        ):
            break
        # 旧节点 choose / choose_2 / … / choose_6：升级确认弹窗（这里点的是对应的坐标）
        if not _点(ctx, IMG("Research/17.png", roi=升级确认区, point=坐标, delay=3000, desc="升级确认")):
            continue
        # 旧节点 revise / revise_2 / … / revise_6：``Research/105.png`` 出现说明这位不能再升
        if _等到(ctx, IMG("Research/105.png"), 冻结=2000):
            continue
    return True


def 降阶装备(ctx: TaskContext) -> bool:
    """旧节点链 ``descending_one`` → ``choose`` → ``descending_two`` → ``choose_2`` → …（六连降阶）。"""
    点到 = False
    for 节点名, 坐标 in 降阶位:
        if not _点(ctx, OCR("降阶", point=坐标, wait_freezes=2000, desc=f"降阶（旧节点 {节点名}）")):
            continue
        点到 = True
        # 降阶之后的确认弹窗还是旧节点 choose / choose_2 / …（``Research/17.png``）
        _点(ctx, IMG("Research/17.png", roi=升级确认区, delay=3000, desc="降阶确认"))
    return 点到


# ------------------------------------------------------- 雪景寒林图的撤退 / 结束


def 点放弃一(ctx: TaskContext) -> bool:
    """旧节点 ``abandon_one``：返回键（``Research/115.png``）→ ``abandon_two``。"""
    return _点(ctx, IMG("Research/115.png", wait_freezes=2000, desc="放弃本局（一）"))


def 点放弃二(ctx: TaskContext) -> bool:
    """旧节点 ``abandon_two``：弹出确认的「放弃」（``Research/116.png``，target 760,430）。"""
    return _点(ctx, IMG("Research/116.png", point=(760, 430), delay=2000, desc="放弃本局（二）"))


def 点中途退出一(ctx: TaskContext) -> bool:
    """旧节点 ``without_one``：中途退出面板（``Research/110.png``）→ ``without_two``。"""
    return _点(ctx, IMG("Research/110.png", delay=2000, desc="中途退出（一）"))


def 点中途退出二(ctx: TaskContext) -> bool:
    """旧节点 ``without_two``：点「中途退出」（target 770,430）→ ``without_three``/降阶/升级。"""
    return _点(ctx, OCR("中途退出", point=(770, 430), delay=2000, desc="中途退出（二）"))


def 点中途退出三(ctx: TaskContext) -> bool:
    """旧节点 ``without_three``：再确认一次中途退出（``Research/110.png``）。"""
    return _点(ctx, IMG("Research/110.png", delay=2000, desc="中途退出（三）"))


def 点获得文物(ctx: TaskContext) -> bool:
    """旧节点 ``cultural_relic``：事件奖励「获得文物」→ ``stwoage`` → ``terminal``。"""
    return _点(ctx, OCR("获得文物", roi=(347, 0, 610, 314), delay=5000, desc="获得文物"))


def 点收纳(ctx: TaskContext) -> bool:
    """旧节点 ``stwoage``：把文物「收纳」起来（roi 733,402,547,318）。"""
    return _点(ctx, OCR("收纳", roi=(733, 402, 547, 318), delay=2000, desc="收纳文物"))


def 点回主页(ctx: TaskContext) -> bool:
    """旧共用节点 ``home``（定义在 ``7_(03)allin.json``）：点 ``Startup/10.png`` 回主页。

    旧 ``home.next`` 是 ``stop``（``StopTask``）—— 所以点到它就说明整局收工了。
    """
    return _点(ctx, IMG("Startup/10.png", desc="回主页"), 前置冻结=1000)


def 点结束研学(ctx: TaskContext) -> bool:
    """旧节点 ``terminal`` → ``quit_research`` → ``home``：本局打完，退出研学界面。

    ``quit_research``（OCR「先行版」，target 240,40）是活动界面偶尔会弹的提示。
    """
    if not _点(ctx, IMG("Research/80.png", point=(1200, 590), delay=3000, desc="结束研学")):
        return False
    _扫(ctx, 点先行版, 点回主页, handle_exceptions, 超时=20_000, 说明="退出研学界面")
    return True


def 点先行版(ctx: TaskContext) -> bool:
    """旧节点 ``quit_research``：活动提示里的「先行版」（target 240,40），没有 next。"""
    return _点(ctx, OCR("先行版", point=(240, 40), desc="点先行版提示"))


# ------------------------------------------------------- 雪景寒林图的战斗


#: 战斗前要选的词条（旧节点 ``front_one`` … ``front_ten``，按旧图的先后顺序）。
战斗词条 = (
    ("front_one", "怒焰"),
    ("front_one_2", "快速启动"),
    ("front_two", "会心一击"),
    ("front_three", "自愈"),
    ("front_four", "奔袭"),
    ("front_four_2", "立盾为护"),
    ("front_four_3", "对群弱点"),
    ("front_four_4", "熟练技巧"),
    ("front_five", "骁勇"),
    ("front_six", "曜斩"),
    ("front_seven", "远程精通"),
    ("front_eight", "一击即走"),
    ("front_eight_2", "移动战术"),
    ("front_nine", "同仇敌忾"),
    ("front_ten", "远行"),
)


def 选战斗词条(ctx: TaskContext) -> bool:
    """旧节点 ``front_one`` … ``front_ten``：战斗前把能点的词条挨个点掉。"""
    点过 = False
    for _ in range(6):
        for 节点名, 词 in 战斗词条:
            if _点(ctx, OCR(词, delay=1000, desc=f"选词条 {词}（旧节点 {节点名}）")):
                点过 = True
                break
        else:
            break
    return 点过


def 点差评弹窗(ctx: TaskContext) -> bool:
    """旧节点 ``negative``：评价不佳时的提示（``Research/95.png``）。"""
    return _点(ctx, IMG("Research/95.png", roi=(355, 2, 670, 186), delay=5000, desc="评价不佳提示"))


def 点战斗新状态(ctx: TaskContext) -> bool:
    """旧节点 ``war_new_state``：战斗前的状态提示（``Research/58.png``）。"""
    return _点(ctx, IMG("Research/58.png", roi=(485, 23, 312, 108), delay=5000, desc="战斗新状态"))


def 点同意二(ctx: TaskContext) -> bool:
    """旧节点 ``agree_2``：词条选完的「同意」（``Research/83.png``）。"""
    return _点(ctx, IMG("Research/83.png", delay=2000, desc="同意（战斗）"))


def 点战斗第一段(ctx: TaskContext) -> bool:
    """旧节点 ``war_five``：战斗结算第一段（``Research/33.png``）。"""
    return _点(ctx, IMG("Research/33.png", roi=(649, 514, 631, 206), wait_freezes=7000, desc="战斗第一段"))


def 点战斗第二段(ctx: TaskContext) -> bool:
    """旧节点 ``war_six``：战斗结算第二段（``Research/34.png``）。"""
    return _点(ctx, IMG("Research/34.png", roi=(649, 514, 631, 206), delay=7000, desc="战斗第二段"))


def 点提醒一(ctx: TaskContext) -> bool:
    """旧节点 ``remind_one``：战斗提示面板（``Research/77.png``）×1。"""
    return _点(ctx, IMG("Research/77.png", delay=3000, desc="战斗提示 1"))


def 点提醒二(ctx: TaskContext) -> bool:
    """旧节点 ``remind_two``：战斗提示面板 ×2。"""
    return _点(ctx, IMG("Research/77.png", delay=3000, desc="战斗提示 2"))


def 点提醒三(ctx: TaskContext) -> bool:
    """旧节点 ``remind_three``：战斗提示面板 ×3。"""
    return _点(ctx, IMG("Research/77.png", delay=5000, desc="战斗提示 3"))


def 点敌方行动(ctx: TaskContext) -> bool:
    """旧节点 ``enemy-action``：等「敌方」行动提示（``DoNothing`` + 5 秒）。"""
    return _等到(ctx, OCR("敌方", desc="敌方行动提示")) and _等(ctx, 5000)


def 点自动(ctx: TaskContext) -> bool:
    """旧节点 ``automatic``：点自动战斗（target 1235,160）。"""
    return _点(ctx, OCR("自动", point=(1235, 160), delay=3000, desc="点自动"))


def 等战斗播报(ctx: TaskContext) -> bool:
    """旧节点 ``remind_all``：战斗里循环等「代班 / 敌方」播报（``DoNothing``，等 30 秒）。

    旧节点写着 ``timeout: 150000``，所以这里是「出现就等 30 秒」，由调用方的
    :func:`_扫` 负责超时。
    """
    if not ctx.look(OCR(["代班", "敌方"], desc="战斗播报")):
        return False
    return _等(ctx, 30000)


def 点战斗确定(ctx: TaskContext) -> bool:
    """旧节点 ``war_seven``：战斗结束的「确定」。"""
    return _点(ctx, OCR("确定", roi=(845, 600, 280, 120), delay=5000, desc="战斗结束确定"))


def 点战败(ctx: TaskContext) -> bool:
    """旧节点 ``fail``：战斗失败时的「完美评价」按钮（target 760,430）。"""
    return _点(ctx, OCR("完美评价", point=(760, 430), delay=5000, desc="失败处理"))


def 打研学战斗(ctx: TaskContext) -> bool:
    """旧节点 ``war_one`` → ``war_two``/``war_three``/``war_four`` → ``war_five`` →
    ``war_six`` → ``remind_*`` → ``war_seven`` → ``fail``：雪景寒林图的一场战斗。

    函数入口就是旧节点 ``war_one``（``Research/30.png``，``DoNothing`` 等 7 秒）。
    """
    # 旧节点 war_one：战斗准备界面（DoNothing + post_wait_freezes 7000）
    if not _等到(ctx, IMG("Research/30.png", desc="战斗准备界面"), 冻结=7000):
        return False
    # 旧 war_one.next = [war_two, war_three, war_four, war_five, negative, war_new_state, advance_four]
    #   评价「中」→ war_two → negative → war_five
    #   评价「良」→ war_three → war_new_state
    #   评价「优」→ war_four → 选词条 → agree_2 → war_new_state
    if _点(ctx, OCR("中", roi=战斗评价区, wait_freezes=2000, desc="评价：中")):  # war_two
        点差评弹窗(ctx)  # 旧节点 negative
    elif _点(ctx, OCR("良", roi=战斗评价区, wait_freezes=2000, desc="评价：良")):  # war_three
        点战斗新状态(ctx)  # 旧节点 war_new_state
    elif _点(ctx, OCR("优", roi=战斗评价区, delay=2000, desc="评价：优")):  # war_four
        选战斗词条(ctx)  # 旧节点 front_one … front_ten
        点同意二(ctx)  # 旧节点 agree_2
        点战斗新状态(ctx)  # 旧节点 war_new_state
    # 旧节点 war_five / war_six：两段结算画面
    if not 点战斗第一段(ctx):
        return False
    if not 点战斗第二段(ctx):
        return False
    # 旧 war_six.next = [remind_one, remind_all, automatic]
    _扫(
        ctx,
        点提醒一,
        点提醒二,
        点提醒三,
        点自动,
        点敌方行动,
        等战斗播报,
        handle_exceptions,
        超时=180_000,
        说明="战斗自动播报",
    )
    # 旧 remind_*.next / war_seven / fail
    if not 点战斗确定(ctx):
        return False
    ctx.tap(IMG("Research/95.png", roi=(355, 2, 670, 186), delay=5000, desc="战斗失败提示"))
    return True


# ======================================================================
# 雪景寒林图的主循环
# ======================================================================

#: 旧 ``advance_two`` / ``advance_three`` / ``advance_four`` 三张 next 表的并集 ——
#: 「地图上现在能点什么」。
地图表: tuple[Step, ...] = (
    # 事件（标题 + 选项）
    点迷雾,
    点迷雾选项,
    点风雪之途,
    点风雪之途选项,
    点山雪之约,
    点山雪之约选项,
    点巡雪山,
    点巡雪山选项,
    点再遇寒雪,
    点再遇寒雪选项,
    点日出东山,
    点日出东山选项,
    点小心脚下,
    点小心脚下选项,
    点线路规划,
    点线路规划选项,
    点杂学之用,
    点杂学之用选项,
    点护林小屋,
    点护林小屋选项,
    点神秘快递,
    点神秘快递选项,
    点画性大发,
    点画性大发选项,
    # 事件结果 / 奖励
    点宿命,
    点完美,
    点继续,
    点关键词,
    点获得物资,
    # 前进
    点前进一_男,
    点前进一_女,
    点前进二_男,
    点前进二_女,
    点前进三_男,
    点前进三_女,
    点前进四_男,
    点前进四_女,
    点前进五_男,
    点前进五_女,
    点前进六_男,
    点前进六_女,
    点前进七_男,
    点前进七_女,
    点前进八_男,
    点前进八_女,
    点前进九_男,
    点前进九_女,
    点不可以往这里,
    点前往,
    # 升级 / 降阶
    升级装备,
    降阶装备,
    # 战斗
    打研学战斗,
    # 文物与撤退
    点获得文物,
    点收纳,
    点放弃一,
    点放弃二,
    点中途退出一,
    点中途退出二,
    点中途退出三,
    # 结束本局（走到这里就跳出循环）
    点结束研学,
)

#: 走到这个节点就说明本局结束（旧节点 ``terminal`` 之后是 ``home`` → ``stop``）。
结束节点 = (点结束研学,)


def 推进研学地图(ctx: TaskContext, 表: Sequence[Step]) -> bool:
    """旧 ``advance_two``/``advance_three``/``advance_four`` 那张大表的主循环。

    旧 pipeline 的逻辑是「把这几个识别挨个试一遍，谁先命中就做谁，做完再看下一张表」；
    这里换成一个 ``while`` 循环反复扫同一张并集表 —— 表里的节点各自把动作做完，
    所以不需要递归，也不会越跑越深。扫不到东西就顺手处理一下通用干扰。
    """
    while not ctx.cancelled:
        ctx.check_cancel()
        命中 = ctx.tap_first(*表)
        if 命中 is None:
            if handle_exceptions(ctx):
                continue
            ctx.screen.sleep(600)
            continue
        if 命中 in 结束节点:
            return True
    return False


def 走雪景寒林图(ctx: TaskContext) -> bool:
    """旧节点链 ``snowscape`` → ``buff-one`` → 技能 → ``agree`` → ``new_state`` → 地图主循环。"""
    if not _扫(
        ctx,
        点雪景寒林图,
        点初始buff,
        点神射,
        点炽刀,
        点术法精通,
        点同意,
        点新状态,
        点前进一_男,
        点前进一_女,
        handle_exceptions,
        超时=180_000,
        说明="进入雪景寒林图并选初始 buff",
    ):
        return False
    return 推进研学地图(ctx, 地图表)


# ======================================================================
# 任务入口
# ======================================================================


@task(
    "博物研学",
    group="日常",
    order=120,
    options=(主题选项, 地图选项, 手动选项),
    description="进博物研学，按选项选主题/地图，把一局（或一局金银研学）跑完",
)
def 博物研学(ctx: TaskContext) -> bool:
    """旧任务「博物研学」（``interface.json`` 里 entry 是 ``museum_Research``）。"""
    if not 进入博物研学(ctx):
        ctx.log.warning("没找到博物研学入口")
        return False
    # 旧节点 museum.next = [Research-week, choose_theme, museum, [JumpBack]Exception-*]
    _扫(ctx, 点研学周常, 点博物入口, handle_exceptions, 超时=30_000, 说明="打开研学主题页")
    return 选择研学主题(ctx)
