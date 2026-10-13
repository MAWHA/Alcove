"""演训：进演训界面 → 选关卡大类 → 选具体关卡 → 选打几次 → 打完收尾。

移植自旧流水线 ``7_training.json``（16 节点）+ ``7_(02)level.json``（6 节点）+
``7_(03)allin.json``（34 节点），任务 key 是 ``演训``（entry ``kaishi``）。

旧写法里三个「空节点」纯粹是为了让 option 覆盖它的 ``next`` 来选分支：

* ``StartTraining`` 的 next 被 ``选择关卡-演训`` 的 8 个 case 分别改写；
* ``xuanze`` 的 next 被 ``打哪个-演训`` 的 5 个 case 分别改写；
* ``fast`` 的 next 被 ``选择战斗次数`` 的 6 个 case 分别改写。

这些绕圈在 Python 里没有任何必要 —— 直接读选项值、查表调对应的函数即可，
所以本模块**没有** ``StartTraining`` / ``xuanze`` / ``fast`` 对应的函数；
它们的「分支」都变成了下面那几张 ``dict``。

另外 ``7_(03)allin.json`` 结尾那条 ``exit`` → ``home`` → ``stop`` 三个节点只
表示「任务到此结束」，Python 里就是函数 ``return True``，同样不需要写出来。
"""

from __future__ import annotations

from MWATools.MWATask import (
    Choice,
    IMG,
    OCR,
    Option,
    TaskContext,
    handle_exceptions,
    task,
)

# --------------------------------------------------------------------- 常量

#: 演训里「打一次」这类分支最多重打几次。旧流水线靠 ``Start1`` 的递归 next 兜底，
#: 完全没有上限；纯 Python 循环必须自己划一条界，免得体力耗光后无限重打。
最多重打次数 = 20

#: 「全部体力」分支的上限。它的退出条件是「速通按钮再也点不到」，
#: 这个界只是防呆，正常打不到。
最多连续速通次数 = 99


# --------------------------------------------------------------------- 选项
#
# 旧 ``interface.json`` 里这三条 option 都没有写 ``default_case``，
# 所以默认值一律取第一个 case（和 ``MWATaskPipeline.default_case`` 的行为一致）。

哪类关卡 = Option(
    "选择关卡-演训",
    label="选择关卡-演训",
    kind="select",
    default="冬谷币",
    choices=(
        Choice("冬谷币"),
        Choice("教材"),
        Choice("装备"),
        Choice("宿卫"),
        Choice("构术"),
        Choice("远击"),
        Choice("轻锐"),
        Choice("战略"),
    ),
    description="演训的第一层：先选资源/材料，还是选某一职业的教材",
)

哪个关卡 = Option(
    "打哪个-演训",
    label="打哪个-演训",
    kind="select",
    default="第一关（子）（演训用）",
    choices=(
        Choice("第一关（子）（演训用）"),
        Choice("第二关（丑）（演训用）"),
        Choice("第三关（寅）（演训用）"),
        Choice("第四关（卯）（演训用）"),
        Choice("第五关（辰）（演训用）"),
    ),
    description="演训的第二层：五个关卡按天干地支标示",
)

三次次数选项 = Option(
    "选择战斗次数",
    label="选择战斗次数",
    kind="select",
    default="打一次（速通没解锁专用）",
    choices=(
        Choice("打一次（速通没解锁专用）"),
        Choice("打一次（速通解锁专用）"),
        Choice("打两次（速通解锁专用）"),
        Choice("打四次（速通解锁专用）"),
        Choice("打十次（速通解锁专用）"),
        Choice("全部体力（速通解锁专用）"),
        Choice("非战斗选项选择这个(活动“良宵百载”专用！！！）"),
        Choice("华灯夜选择这个(活动“良宵百载”专用！！！）"),
    ),
    description="打几次；「速通没解锁」= 老老实实打一局，其余走速通",
)


# --------------------------------------------------------------------- 进界面


def 进演训(ctx: TaskContext) -> bool:
    """旧节点 ``EnterTraining``：点主页的演训图标，等演训界面起来。"""
    if not ctx.tap(
        IMG("Mainpage/training.png", delay=3000, desc="主页演训图标")
    ):
        return False
    # 旧 next：[StartTraining, 两个 Exception-handling]
    return bool(
        ctx.scan(点今日开放, handle_exceptions, timeout=20_000, desc="等演训界面")
    )


def 点今日开放(ctx: TaskContext) -> bool:
    """旧节点 ``StartTraining``：列表里的「今日开放」，点它进具体关卡列表。

    这句话认得出来就说明排在第一个的演训已经解锁；点在固定坐标 (260, 295)
    （旧 JSON 的 ``target: [260, 295, 0, 0]``）。

    注意：``StartTraining`` 本来是「按 option 选 8 个大类」的空节点，这层分支
    已经搬进 ``演训`` 主函数了，这里只负责「点进去」这一件事。
    """
    return ctx.tap(
        OCR(
            "今日开放",
            point=(260, 295),
            delay=2000,  # 旧 post_delay: 2000
            desc="进入今日开放的演训",
        )
    )


# --------------------------------------------------------------------- 选哪类关卡
#
# 旧节点 ``Cash`` / ``Experience`` / ``Weapon`` 直接点自己的文字；
# ``Defender`` / ``Caster`` / ... / ``Tactical`` 则是「先点 Mainpage/110.png 展开，
# 再点职业名」（各自还多一个 ``Xxx1`` 节点）。这里原样保留这两段式。


def 点冬谷币(ctx: TaskContext) -> bool:
    """旧节点 ``Cash``。"""
    return ctx.tap(OCR("冬谷币", desc="冬谷币）"))


def 点教材(ctx: TaskContext) -> bool:
    """旧节点 ``Experience``。"""
    return ctx.tap(OCR("教材", desc="教材"))


def 点装备(ctx: TaskContext) -> bool:
    """旧节点 ``Weapon``。"""
    return ctx.tap(OCR("装备", desc="装备"))


def 展开职业列表(ctx: TaskContext) -> bool:
    """旧节点 ``Defender`` / ``Caster`` / ``Ranger`` / ``LightMelee`` / ``Tactical``。

    这五个节点长得一模一样：都是点 ``Mainpage/110.png`` 把职业那一栏展开。
    """
    return ctx.tap(IMG("Mainpage/110.png", desc="展开职业列表"))


def _点职业(ctx: TaskContext, 名称: str) -> bool:
    """旧节点 ``Defender1`` / ``Caster1`` / ``Ranger1`` / ``LightMelee1`` / ``Tactical1``。"""
    return ctx.tap(OCR(名称, desc=名称))


def 点宿卫(ctx: TaskContext) -> bool:
    """旧节点 ``Defender1``（先 ``Defender`` 展开）。"""
    return 展开职业列表(ctx) and _点职业(ctx, "宿卫")


def 点构术(ctx: TaskContext) -> bool:
    """旧节点 ``Caster1``（先 ``Caster`` 展开）。"""
    return 展开职业列表(ctx) and _点职业(ctx, "构术")


def 点远击(ctx: TaskContext) -> bool:
    """旧节点 ``Ranger1``（先 ``Ranger`` 展开）。"""
    return 展开职业列表(ctx) and _点职业(ctx, "远击")


def 点轻锐(ctx: TaskContext) -> bool:
    """旧节点 ``LightMelee1``（先 ``LightMelee`` 展开）。"""
    return 展开职业列表(ctx) and _点职业(ctx, "轻锐")


def 点战略(ctx: TaskContext) -> bool:
    """旧节点 ``Tactical1``（先 ``Tactical`` 展开）。"""
    return 展开职业列表(ctx) and _点职业(ctx, "战略")


#: 「选择关卡-演训」的 8 个 case → 对应的点法。旧 JSON 是靠覆盖 ``StartTraining``
#: 的 next 来选，这里就是一张普通查表。
关卡大类 = {
    "冬谷币": 点冬谷币,
    "教材": 点教材,
    "装备": 点装备,
    "宿卫": 点宿卫,
    "构术": 点构术,
    "远击": 点远击,
    "轻锐": 点轻锐,
    "战略": 点战略,
}


# --------------------------------------------------------------------- 选具体关卡
#
# 旧 ``xuanze`` 的 next 是五个 SelectStage，靠 option 覆盖来「选中」其中一个。
# 这里的差异只有两处：识别哪个字、点击位置从识别框往上挪多少（target_offset）。

#: 旧节点 → (识别词, target_offset)。坐标偏移直接照抄 JSON。
关卡坐标 = {
    "第一关（子）（演训用）": ("子", (0, -40, 0, 0)),   # 旧节点 SelectStage01
    "第二关（丑）（演训用）": ("丑", (0, -50, 0, 0)),   # 旧节点 SelectStage02
    "第三关（寅）（演训用）": ("寅", (0, -50, 0, 0)),   # 旧节点 SelectStage03
    "第四关（卯）（演训用）": ("卯", (0, -50, 0, 0)),   # 旧节点 SelectStage04
    "第五关（辰）（演训用）": ("辰", (0, -50, 0, 0)),   # 旧节点 SelectStage05
}


def 选中关卡(ctx: TaskContext, 关卡名: str) -> bool:
    """旧节点 ``SelectStage01`` ~ ``SelectStage05``。

    五个节点的唯一差别就是识别词和 ``target_offset``，所以合成一个带参数的函数。
    """
    字, 偏移 = 关卡坐标.get(关卡名, 关卡坐标["第一关（子）（演训用）"])
    return ctx.tap(OCR(字, offset=偏移, desc=f"选关卡 {字}"))


# --------------------------------------------------------------------- 打法：一步步点界面


def 点开始(ctx: TaskContext) -> bool:
    """旧节点 ``Start1`` / ``Start2``：右下角的「开始」。

    ``post_wait_freezes: 5000`` 表示点完要等画面静止 5 秒 —— 这一下会切进战斗，
    不等的话后面一整套识别都会读到旧画面。
    """
    return ctx.tap(OCR("开始", wait_freezes=5000, desc="点开始"))


def 点代班中(ctx: TaskContext) -> bool:
    """旧节点 ``substitute_shifts``：战斗里「敌方代班中」的提示。

    ``action`` 是 ``DoNothing`` —— **只识别，不点击**（点它没有意义，那是句状态文字）。
    旧写法靠 ``next: [rating, substitute_shifts, situation, rating-fail]`` 里的自环
    反复回来等，加上 ``post_delay: 5000`` 每次歇 5 秒，直到「代班中」消失。

    所以这里**故意返回 False**：让外层 ``ctx.scan`` 别停下来，继续等评价/战况出现；
    ``scan`` 下一轮又会认出「代班中」、再歇 5 秒，正好复刻那个自环。
    """
    if not ctx.look(OCR(["敌方", "代班中"])):
        return False
    ctx.screen.sleep(5000)  # 旧 post_delay: 5000
    return False


def 点自动(ctx: TaskContext) -> bool:
    """旧节点 ``allin-automatic``：右上角的「自动」，点它让战斗自己打。"""
    return ctx.tap(
        OCR(
            "自动",
            point=(1235, 160),  # 旧 target: [1235, 160, 0, 0]
            delay=5000,         # 旧 post_delay: 5000
            desc="开自动战斗",
        )
    )


def 点评级(ctx: TaskContext) -> bool:
    """旧节点 ``rating`` / ``rating-fail``：战斗结束后的评级条，点掉它。

    ``rating`` 认的是「评级」（点自己），``rating-fail`` 认的是 roi 里的
    未达成完美评价提示（点固定坐标）—— 两者是在同一个循环里被反复重试的，
    Python 里合并成一次「要么点评级要么点未达成提示」。
    """
    if ctx.tap(
        OCR(
            "评级",
            point=(770, 425),  # 旧 target: [770, 425, 0, 0]
            delay=3000,        # 旧 post_delay: 3000
            desc="点评级",
        )
    ):
        return True
    return ctx.tap(
        OCR(
            ["未能", "达到", "完美", "评价", "结算"],
            roi=(406, 248, 459, 227),  # 旧节点 rating-fail 的 roi
            point=(775, 435),          # 旧 target: [775, 435, 0, 0]
            delay=3000,                # 旧 post_delay: 3000
            desc="关掉未达成提示",
        )
    )


def 点确定(ctx: TaskContext) -> bool:
    """旧节点 ``situation``：战斗结算里那个「确定」。

    旧节点自己有个 ``next: [exit, situation]``（没点掉就再点一次），
    这里交给外层的 ``scan`` 反复试，效果一样但不递归。
    """
    return ctx.tap(OCR("确定", desc="点确定"))


def _等结算再确定(ctx: TaskContext) -> bool:
    """旧节点 ``settlement`` / ``allin-settlement``：先等「结算完成」再点确定。

    ``pre_wait_freezes: 2000`` 是等这个面板静止，``target: [1115, 635, 0, 0]``
    是右下角固定位置。没等到「结算完成」就返回 False，让外层 scan 继续试。
    """
    if not ctx.look(OCR("结算完成")):
        return False
    ctx.screen.wait_freezes(time=2000)
    ctx.screen.click((1115, 635), delay=1000, desc="结算完成，点掉")
    return True


def 走战斗流程(ctx: TaskContext) -> bool:
    """旧节点 ``Start1`` → ``Start2`` → ``situation`` 这条战斗链。

    原来的 next 是一张「点开始 → 等代班/开自动 → 点评级 → 点确定」的图；
    这里写成顺序调用，靠每一步自己返回 True/False 表示有没有做成。
    """
    if not 点开始(ctx):
        return False  # 没找到「开始」，说明已经不在战斗准备了
    ctx.scan(点代班中, 点自动, 点评级, timeout=60_000, desc="等战斗结束")
    # 旧链路最后收敛到 situation；没等到就交给外层重打一次。
    return bool(ctx.scan(点确定, _等结算再确定, timeout=30_000, desc="等结算确定"))


def 收尾(ctx: TaskContext) -> bool:
    """旧节点 ``exit`` → ``home``（``stop`` 只表示任务结束）。

    ``exit`` 是 ``Collect/06.png``（和全局的 ``QUIT`` 同一张图），
    ``home`` 是 ``Startup/10.png``；两张都带 ``pre_wait_freezes``。
    """
    if not ctx.tap(IMG("Collect/06.png", wait_freezes=1000, desc="关掉结算面板")):
        return False
    return ctx.tap(IMG("Startup/10.png", wait_freezes=1000, desc="回主页"))


# --------------------------------------------------------------------- 打法：速通一条龙


def 点速通(ctx: TaskContext) -> bool:
    """旧节点 ``fast``：界面右下角的「速通」按钮。

    这个节点的 ``next`` 被 ``选择战斗次数`` 的 case 覆盖，是「选打几倍速通」的
    开关；点击本身还带着 ``pre_delay: 2000`` / ``post_delay: 3000``。
    """
    ctx.screen.sleep(2000)  # 旧 pre_delay: 2000
    return ctx.tap(
        OCR(
            "速通",
            point=(1030, 660),  # 旧 target: [1030, 660, 0, 0]
            delay=3000,         # 旧 post_delay: 3000
            desc="点速通",
        )
    )


def 点速通结算(ctx: TaskContext) -> bool:
    """旧节点 ``CompleteSpeedrun``：速通结算面板上的 ``Speedrun/12.png``。"""
    return ctx.tap(IMG("Speedrun/12.png", desc="速通结算"))


def 点好感已满(ctx: TaskContext) -> bool:
    """旧节点 ``goodwill``：好感已满的提示，按它给的 ``target`` 矩形点掉。

    旧节点是「在 roi 里识别到好感已满，然后点 ``target: [770, 430, 510, 290]``
    这个矩形」—— 也就是说点的地方不跟着识别框走，所以先 ``look`` 再点固定矩形。
    """
    if not ctx.look(OCR("好感已满", roi=(485, 280, 324, 82))):
        return False
    return ctx.screen.click((770, 430, 510, 290), desc="好感已满：点掉提示")


def 点结算(ctx: TaskContext) -> bool:
    """旧节点 ``settlement``：等结算完成 → 点右下角固定位置。"""
    return bool(_等结算再确定(ctx))


def 收尾速通(ctx: TaskContext) -> bool:
    """旧节点 ``exit`` → ``home``：速通一条龙的收尾。"""
    return 收尾(ctx)


def 速通一条龙(ctx: TaskContext) -> bool:
    """旧 ``CompleteSpeedrun`` → ``goodwill`` → ``settlement`` → ``exit``。

    旧 next 是 ``[goodwill, settlement]``，``goodwill`` 自己又能绕回
    ``CompleteSpeedrun``；合并成「点结算面板 → 顺手关掉好感提示 → 点确定完成
    → 退出界面」，一趟走完。
    """
    if not ctx.scan(点速通结算, timeout=20_000, desc="等速通结算"):
        return False
    # 旧 goodwill / settlement 是并列候选，谁先出现就处理谁。
    hit = ctx.scan(点好感已满, 点结算, timeout=30_000, desc="速通结算")
    if hit is None:
        return False
    ctx.scan(点好感已满, timeout=5_000, desc="补关好感提示")
    return 收尾速通(ctx)


def 多倍速通(ctx: TaskContext, 次数: int) -> bool:
    """旧节点 ``Speedrun{2,4,10}x`` + ``AddSpeedrunTime{2,4,10}`` / ``Sub_AddSpeedrunTime*``。

    旧写法是每个倍数四五个节点、节点名靠数字区分；它们的差别只有「点几下多倍
    按钮」和「拿哪张图确认倍率已选满」：

    * ``Speedrun2x``：先试 ``AddSpeedrunTime2``（``Speedrun/13.png``），
      没满就点一下 ``Speedrun/11.png`` 再加，最后都落到 ``CompleteSpeedrun``；
    * ``Speedrun4x`` / ``Speedrun10x`` 同理，只是换成 14.png / 15.png。

    所以这里写成一个循环 + 一张查表，而不是复制三份。
    """
    倍率 = {
        2: ("Speedrun/13.png", (744, 324, 35, 34)),
        4: ("Speedrun/14.png", (746, 323, 33, 32)),
        10: ("Speedrun/15.png", (741, 325, 42, 33)),
    }.get(次数)
    if 倍率 is None:
        return False
    确认图, 确认roi = 倍率

    # 选多倍之前得先点开「速通」按钮（旧节点 fast 是这条链的入口）。
    if not 点速通(ctx):
        return False

    # 旧 Speedrun2x 的 next：[AddSpeedrunTime2, requires_more, Sub_AddSpeedrunTime2, CompleteSpeedrun]
    # 点一下没到目标倍率就再加，最多加 次数 次。
    for _ in range(次数):
        ctx.check_cancel()
        if ctx.look(IMG(确认图, roi=确认roi)):
            break
        if not ctx.tap(IMG("Speedrun/11.png", roi=(830, 275, 125, 115), desc="加一次多倍")):
            break
    # requires_more（体力不够）不改变流程：照样去点结算面板。
    ctx.tap(OCR("需要更多体力", delay=2000, desc="体力不够提示"))
    return 速通一条龙(ctx)


def 速通一次(ctx: TaskContext) -> bool:
    """旧节点 ``Speedrun1x``：点 ``Speedrun/10.png``，然后走速通收尾。"""
    if not 点速通(ctx):
        return False
    if not ctx.tap(
        IMG(
            "Speedrun/10.png",
            point=(855, 420),  # 旧 target: [855, 420, 0, 0]
            desc="选一次速通",
        )
    ):
        return False
    return 速通一条龙(ctx)


# --------------------------------------------------------------------- 打法：全部体力


def 点最大多倍(ctx: TaskContext) -> bool:
    """旧节点 ``allin-max``：识别到「最大多倍」就往下走。

    ``action`` 是 ``DoNothing``（点那句文字没用），命中即返回 True 让外层
    转去点 ``Speedrun/12.png`` 的结算弹窗。
    """
    return bool(ctx.look(OCR("最大多倍", desc="已选到最大多倍")))


def 点多倍领取(ctx: TaskContext) -> bool:
    """旧节点 ``allin-CompleteSpeedrun``：``Speedrun/12.png`` 弹窗里的领取。"""
    return ctx.tap(IMG("Speedrun/12.png", desc="多倍结算"))


def 点活力不足收尾(ctx: TaskContext) -> bool:
    """旧节点 ``allin-vitality`` → ``allin-quit``：活力用完后退出。

    ``allin-vitality`` 识别 roi 里的「活力」（``DoNothing``，只为确认），
    ``allin-quit`` 点 ``dst/fork.png``。
    """
    if not ctx.look(OCR("活力", roi=(180, 75, 220, 130))):
        return False
    ctx.screen.sleep(2000)  # 旧 post_delay: 2000
    return ctx.tap(IMG("dst/fork.png", desc="活力不足，退出"))


def 多倍一次(ctx: TaskContext) -> bool:
    """旧节点 ``allin`` → ``allin-settlement``。

    ``allin`` 是 ``Speedrun/11.png``（在 roi 里），点开多倍面板后有两种收场：
    面板弹出到最大倍率（``allin-max``），或者体力不够只剩退出。都处理完返回 True，
    表示「这一轮多倍已经安排好了」。
    """
    if not ctx.tap(
        IMG(
            "Speedrun/11.png",
            roi=(830, 275, 125, 115),
            delay=2000,  # 旧 post_delay: 2000
            desc="点最大多倍",
        )
    ):
        return False
    # 旧 next：[requires_more, allin-max, allin]
    ctx.scan(点最大多倍, 点活力不足收尾, timeout=10_000, desc="等最大多倍")
    if not ctx.tap(IMG("Speedrun/12.png", desc="多倍结算")):
        return False
    ctx.scan(点好感已满, 点结算, timeout=30_000, desc="多倍结算")
    return 收尾速通(ctx)


def 全部体力(ctx: TaskContext) -> bool:
    """旧节点 ``allin`` → ``allin-fast`` → ``allin-vitality`` 这条链。

    旧写法是 ``allin`` 的 next 里套 ``allin-fast`` 再指回 ``allin``（自己套自己），
    靠「速通按钮不再出现」自然停下；这里就是一个普通循环。
    """
    for _ in range(最多连续速通次数):
        ctx.check_cancel()
        # 旧 allin-fast：再点一次「速通」（pre_delay 2000 / post_delay 2000）
        ctx.screen.sleep(2000)
        if not ctx.tap(
            OCR(
                "速通",
                point=(1030, 660),  # 旧 target: [1030, 660, 0, 0]
                delay=2000,         # 旧 post_delay: 2000
                desc="继续速通",
            )
        ):
            return 点活力不足收尾(ctx)  # 点不到速通 = 体力见底，走 allin-vitality
        if not 多倍一次(ctx):
            return 点活力不足收尾(ctx)
    return True


# --------------------------------------------------------------------- 收尾分流
#
# ``选择战斗次数`` 的 6 个战斗 case 分两大类：
#   * 「打一次（速通没解锁专用）」→ Start1，老老实实打一局，失败就重打；
#   * 「打一次/两次/四次/十次/全部体力（速通解锁专用）」→ 速通链，次数决定打几轮。


def 重打直到成功(ctx: TaskContext) -> bool:
    """旧 ``Start1`` 的 ``goodwill`` 分支里那条「回 ``Start1``」的重试。

    旧图是递归的 next，没有上限；循环写法必须自己收口（见 ``最多重打次数``）。
    """
    for _ in range(最多重打次数):
        ctx.check_cancel()
        if 走战斗流程(ctx):
            return True
        ctx.log.info("这一局没走到结算，重试")
    ctx.log.warning("重打 %d 次仍未走到结算，放弃", 最多重打次数)
    return False


def 打一次(ctx: TaskContext) -> bool:
    """``选择战斗次数`` = 打一次（速通没解锁专用）时的分支（旧 ``Start1``）。"""
    if not 点开始(ctx):
        return False
    return 重打直到成功(ctx) or False


#: 旧节点名对照（这几个节点在旧 JSON 里靠尾号区分，这里都收敛进了需要它们的那几个函数，
#: 列在这里免得看代码的人以为漏了）：
#:
#: * ``frequency`` —— 旧 7_(03)allin.json 里那个「option 覆盖 next」的空节点，
#:   分支收在 ``演训`` 本体的 ``打法`` 查表里；
#: * ``allin-goodwill`` / ``allin-CompleteSpeedrun`` —— ``allin`` 链里的好感/结算面板，
#:   由 ``多倍一次`` 复用 ``点好感已满`` + ``_等结算再确定``；
#: * ``AddSpeedrunTime2`` / ``AddSpeedrunTime4`` / ``AddSpeedrunTime10`` 与
#:   ``Sub_AddSpeedrunTime2`` / ``Sub_AddSpeedrunTime4`` / ``Sub_AddSpeedrunTime10``
#:   —— 2 倍 / 4 倍 / 10 倍各两个，由 ``多倍速通`` 的倍率表 + 循环覆盖。
旧节点对照 = (
    "frequency",
    "allin-goodwill",
    "allin-CompleteSpeedrun",
    "AddSpeedrunTime2", "AddSpeedrunTime4", "AddSpeedrunTime10",
    "Sub_AddSpeedrunTime2", "Sub_AddSpeedrunTime4", "Sub_AddSpeedrunTime10",
)

def 按次数速通(ctx: TaskContext, 次数: int) -> bool:
    """按 ``选择战斗次数`` 打固定轮数：1 次走 ``Speedrun1x``，其余走多倍链。"""
    for index in range(次数):
        ctx.check_cancel()
        ctx.step(f"速通第 {index + 1}/{次数} 轮")
        ok = 速通一次(ctx) if 次数 == 1 else 多倍速通(ctx, 次数)
        if not ok:
            return False
    return True


#: 「选择战斗次数」的战斗 case → 对应的打法。两个「良宵百载专用」的 case 不是给
#: 演训/资源用的（它们覆盖的是 ``activity-fail`` 节点），落在下面查表里就是
#: 「不认识」→ 直接放弃，免得误点。
打法 = {
    "打一次（速通没解锁专用）": 打一次,
    "打一次（速通解锁专用）": lambda ctx: 按次数速通(ctx, 1),
    "打两次（速通解锁专用）": lambda ctx: 按次数速通(ctx, 2),
    "打四次（速通解锁专用）": lambda ctx: 按次数速通(ctx, 4),
    "打十次（速通解锁专用）": lambda ctx: 按次数速通(ctx, 10),
    "全部体力（速通解锁专用）": 全部体力,
}


# --------------------------------------------------------------------- 任务


@task(
    "演训",
    group="战斗",
    order=200,
    options=(哪类关卡, 哪个关卡, 三次次数选项),
    description="进演训 → 选关卡 → 按选的次数打（支持速通倍数 / 全部体力）",
)
def 演训(ctx: TaskContext) -> bool:
    """旧任务入口 ``kaishi``。

    旧节点 ``kaishi`` 的 next 是 ``[EnterTraining, StartTraining, 两个异常处理]``，
    其中 ``StartTraining`` 只是「option 覆盖 next 用的空节点」，真正的分支在本函数里：
    先读 ``选择关卡-演训`` 决定点哪一类，再读 ``打哪个-演训`` 决定去哪个关卡。
    """
    ctx.step("打开演训")
    if not ctx.scan(进演训, handle_exceptions, timeout=30_000, desc="打开演训"):
        ctx.log.warning("没找到演训入口，可能不在这套界面里")
        return False

    # 旧 StartTraining 的 next 被 option 覆盖成 8 个大类之一 → 查表挑点法。
    类别 = ctx.text("选择关卡-演训", 哪类关卡.default)
    点法 = 关卡大类.get(类别)
    if 点法 is None:
        ctx.log.warning("不认识的演训关卡类别：%s", 类别)
        return False
    ctx.step(f"选演训类别：{类别}")
    if not ctx.retry(lambda: 点法(ctx), timeout=20_000, desc=f"选 {类别}"):
        return False

    # 旧 xuanze 的 next 被 option 覆盖成 5 个 SelectStage 之一 → 只认对应那个字。
    关卡 = ctx.text("打哪个-演训", 哪个关卡.default)
    ctx.step(f"选关卡：{关卡}")
    if not ctx.retry(
        lambda: 选中关卡(ctx, 关卡), timeout=20_000, desc=f"选 {关卡}"
    ):
        return False

    # 旧 fast 的 next 被 option 覆盖成「打几倍 / 全部体力」→ 查表挑打法。
    # （速通没解锁时界面上根本没有「速通」按钮，那条链走的是 Start1。）
    次数 = ctx.text("选择战斗次数", 三次次数选项.default)
    执行 = 打法.get(次数)
    if 执行 is None:
        ctx.log.warning(
            "「%s」是良宵百载活动专用的次数选项，演训用不了，任务放弃", 次数
        )
        return False
    ctx.step(f"战斗次数：{次数}")
    if not 执行(ctx):
        return False

    # 速通链自己收尾（exit → home）；「打一次」那条链的收尾也在走战斗流程里完成。
    ctx.step("演训结束")
    return True
