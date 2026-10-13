"""资源：进资源界面 → 选章节 → 拖地图找到资源点 → 选第几关 → 速通打完。

移植自旧流水线 ``8_resource.json``（45 节点），任务 key 是 ``资源``
（entry ``resource_all``）。

旧写法里两个「空节点」专门用来让 option 覆盖它的 ``next`` 选分支：

* ``resource_all`` 的 next 被 ``选择关卡-资源`` 的 5 个 case 分别改写成
  ``resource_one`` ~ ``resource_five``（一章一条链）；
* ``resource`` 的 next 被 ``打哪个-资源`` 的 5 个 case 分别改写成
  ``ancient_both_sea_cantonese_often1`` ~ ``5``（点「壹」~「伍」）。

这五条章节链长得几乎一样，只有三处不同：城市名、点哪个坐标的模板图、
以及滑几次地图。所以本模块用**一张查表 + 一个带参数的函数**表达，而不是
把同一段代码抄五遍；同样地，本模块没有 ``resource_all`` / ``resource`` 的
对应函数 —— 它们的「分支」都在 ``章节表`` 和 ``数字`` 这两张表里。

五条链结束后都接到 ``fast``（速通选次数），那一段的逻辑和 ``training.py``
里的一模一样；因为规范第 2 条要求模块之间**不许互相 import**，这里把需要
的几个速通节点在本模块内重新定义了一份（谁坏了都不影响对方）。
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

#: 速通结算那条链最多重试几次（防呆用；旧 pipeline 的 next 没有上限）。
最多重试次数 = 20


# --------------------------------------------------------------------- 选项
#
# 旧 ``interface.json`` 里这两条 option 都没有 ``default_case``，默认取第一个 case。

哪章 = Option(
    "选择关卡-资源",
    label="选择关卡-资源",
    kind="select",
    default="第一章",
    choices=(
        Choice("第一章"),
        Choice("第二章"),
        Choice("第三章"),
        Choice("第四章"),
        Choice("第五章"),
    ),
    description="资源里的第几章（每章对应一座城的地图）",
)

哪个关卡 = Option(
    "打哪个-资源",
    label="打哪个-资源",
    kind="select",
    default="第一关（壹）（资源用）",
    choices=(
        Choice("第一关（壹）（资源用）"),
        Choice("第二关（贰）（资源用）"),
        Choice("第三关（叁）（资源用）"),
        Choice("第四关（肆）（资源用）"),
        Choice("第五关（伍）（资源用）"),
    ),
    description="地图上第几个资源点，界面用「壹贰叁肆伍」标示",
)

#: ``选择战斗次数`` 这个 option 在 interface.json 里是**三个任务共用**的
#: （演训、资源、良宵百载），所以资源这边声明时必须和 training.py 保持一致，
#: 否则同一个 key 在两处登记的 choices 不同，GUI 会按加载顺序取到其中一份。
#: 8 个 case 全部照抄（包括那两个活动专用、资源用不上的）。
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


# --------------------------------------------------------------------- 速通（和 training.py 同源，按规范在本模块内自持一份）


def 点速通(ctx: TaskContext) -> bool:
    """旧节点 ``fast``：界面右下角的「速通」按钮。"""
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
    """旧节点 ``goodwill``：在 roi 里认出好感已满，然后点它给的 ``target`` 矩形。"""
    if not ctx.look(OCR("好感已满", roi=(485, 280, 324, 82))):
        return False
    return ctx.screen.click((770, 430, 510, 290), desc="好感已满：点掉提示")


def _等结算再确定(ctx: TaskContext) -> bool:
    """旧节点 ``settlement``：等面板静止（``pre_wait_freezes: 2000``）再点确定。"""
    if not ctx.look(OCR("结算完成")):
        return False
    ctx.screen.wait_freezes(time=2000)
    ctx.screen.click((1115, 635), delay=1000, desc="结算完成，点掉")
    return True


def 收尾速通(ctx: TaskContext) -> bool:
    """旧节点 ``exit`` → ``home``（``stop`` 只表示任务结束）。"""
    if not ctx.tap(IMG("Collect/06.png", wait_freezes=1000, desc="关掉结算面板")):
        return False
    return ctx.tap(IMG("Startup/10.png", wait_freezes=1000, desc="回主页"))


def 速通一条龙(ctx: TaskContext) -> bool:
    """旧 ``CompleteSpeedrun`` → ``goodwill`` → ``settlement`` → ``exit`` 这条链。"""
    if not ctx.scan(点速通结算, timeout=20_000, desc="等速通结算"):
        return False
    if ctx.scan(点好感已满, _等结算再确定, timeout=30_000, desc="速通结算") is None:
        return False
    ctx.scan(点好感已满, timeout=5_000, desc="补关好感提示")
    return 收尾速通(ctx)


def 点最大多倍(ctx: TaskContext) -> bool:
    """旧节点 ``allin-max``：识别到「最大多倍」就往下走（``DoNothing``，不点击）。"""
    return bool(ctx.look(OCR("最大多倍", desc="已选到最大多倍")))


def 点活力不足收尾(ctx: TaskContext) -> bool:
    """旧节点 ``allin-vitality`` → ``allin-quit``：活力用完后退出。"""
    if not ctx.look(OCR("活力", roi=(180, 75, 220, 130))):
        return False
    ctx.screen.sleep(2000)  # 旧 post_delay: 2000
    return ctx.tap(IMG("dst/fork.png", desc="活力不足，退出"))


def 多倍一次(ctx: TaskContext) -> bool:
    """旧节点 ``allin`` → ``allin-settlement``：点开多倍面板 → 结算 → 退出。"""
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
    ctx.scan(点好感已满, _等结算再确定, timeout=30_000, desc="多倍结算")
    return 收尾速通(ctx)


def 速通一次(ctx: TaskContext) -> bool:
    """旧节点 ``Speedrun1x``：点 ``Speedrun/10.png``，然后走速通收尾。"""
    if not 点速通(ctx):
        return False
    if not ctx.tap(
        IMG("Speedrun/10.png", point=(855, 420), desc="选一次速通")
    ):
        return False
    return 速通一条龙(ctx)


def 多倍速通(ctx: TaskContext, 次数: int) -> bool:
    """旧节点 ``Speedrun{2,4,10}x`` + ``AddSpeedrunTime*`` / ``Sub_AddSpeedrunTime*``。

    旧写法一个倍数要四五个节点，差别只有「拿哪张图确认倍率选满」；这里用一张表
    收敛，循环里最多点 ``次数`` 下多倍按钮。
    """
    倍率 = {
        2: ("Speedrun/13.png", (744, 324, 35, 34)),
        4: ("Speedrun/14.png", (746, 323, 33, 32)),
        10: ("Speedrun/15.png", (741, 325, 42, 33)),
    }.get(次数)
    if 倍率 is None:
        return False
    确认图, 确认roi = 倍率

    if not 点速通(ctx):
        return False
    for _ in range(次数):
        ctx.check_cancel()
        if ctx.look(IMG(确认图, roi=确认roi)):
            break
        if not ctx.tap(IMG("Speedrun/11.png", roi=(830, 275, 125, 115), desc="加一次多倍")):
            break
    ctx.tap(OCR("需要更多体力", delay=2000, desc="体力不够提示"))
    return 速通一条龙(ctx)


def 点开始(ctx: TaskContext) -> bool:
    """旧节点 ``Start1``：右下角的「开始」（速通没解锁时的打法）。"""
    return ctx.tap(OCR("开始", wait_freezes=5000, desc="点开始"))


def 点代班中(ctx: TaskContext) -> bool:
    """旧节点 ``substitute_shifts``：战斗里「敌方代班中」的提示。

    ``action`` 是 ``DoNothing`` —— 只识别不点（那是句状态文字）。
    旧写法靠 ``next`` 里的自环 + ``post_delay: 5000`` 反复回来等它消失，
    所以这里**故意返回 False**，让外层 ``ctx.scan`` 继续等其他候选。
    """
    if not ctx.look(OCR(["敌方", "代班中"])):
        return False
    ctx.screen.sleep(5000)  # 旧 post_delay: 5000
    return False


def 点自动(ctx: TaskContext) -> bool:
    """旧节点 ``allin-automatic``：右上角的「自动」。"""
    return ctx.tap(
        OCR("自动", point=(1235, 160), delay=5000, desc="开自动战斗")
    )


def 点评级(ctx: TaskContext) -> bool:
    """旧节点 ``rating`` / ``rating-fail``：战斗结束后的评级 / 未达成提示。"""
    if ctx.tap(
        OCR("评级", point=(770, 425), delay=3000, desc="点评级")
    ):
        return True
    return ctx.tap(
        OCR(
            ["未能", "达到", "完美", "评价", "结算"],
            roi=(406, 248, 459, 227),
            point=(775, 435),
            delay=3000,
            desc="关掉未达成提示",
        )
    )


def 点确定(ctx: TaskContext) -> bool:
    """旧节点 ``situation``：战斗结算里那个「确定」。"""
    return ctx.tap(OCR("确定", desc="点确定"))


def 走战斗流程(ctx: TaskContext) -> bool:
    """旧 ``Start1`` → ``Start2`` → ``situation`` 这条战斗链（速通没解锁时）。"""
    if not 点开始(ctx):
        return False
    ctx.scan(点代班中, 点自动, 点评级, timeout=60_000, desc="等战斗结束")
    return bool(ctx.scan(点确定, _等结算再确定, timeout=30_000, desc="等结算确定"))


def 重打直到成功(ctx: TaskContext) -> bool:
    """旧 ``goodwill`` 里那条「回到 ``Start1``」的重试，用循环收口。"""
    for _ in range(最多重试次数):
        ctx.check_cancel()
        if 走战斗流程(ctx):
            return True
        ctx.log.info("这一局没走到结算，重试")
    ctx.log.warning("重打 %d 次仍未走到结算，放弃", 最多重试次数)
    return False


# --------------------------------------------------------------------- 章节链
#
# 旧写法：``resource_one`` → (``execute_one`` | ``come_ancient`` | ``big_map_one``)
# → ``ancient`` → ``hide_one`` → ``Swipe1`` → ``Swipe2`` → ``Swipe3`` → ``resource``。
# 五章的差别只有：城市名、资源点模板（resource/02~07.png）与它的 roi、
# 以及拖地图要滑几下。下面这张表就是那五条链。


def _执行(ctx: TaskContext) -> bool:
    """旧节点 ``execute_one`` / ``execute_two`` / ``execute_three`` /
    ``execute_four`` / ``execute_five``：面板上的「执行」。"""
    return ctx.tap(OCR("执行", delay=2000, desc="点执行"))


def _大地图(ctx: TaskContext) -> bool:
    """旧节点 ``big_map_one`` / ``big_map_two`` / ``big_map_three`` /
    ``big_map_four`` / ``big_map_five``：点「大地图」直接进全图。"""
    return ctx.tap(OCR("大地图", delay=3000, desc="打开大地图"))


def _城市名(ctx: TaskContext, 名称: str) -> bool:
    """旧节点 ``come_ancient`` / ``Biandu`` / ``deut_sea`` / ``cantonese_prefecture`` / ``often_quiet``。

    这五个节点都是「在界面上认一下城市名」然后去滑地图 —— ``action`` 缺省，
    而 maafw 的默认动作是 ``DoNothing``，**只识别不点**（点城市名会弹出城市面板，是错的）。
    旧 JSON 里二三四五章这几个节点还带 ``post_delay``（1000），这里用 ``ctx.screen.sleep`` 补上。
    """
    if ctx.look(OCR(名称, desc=f"确认到了{名称}")):
        ctx.screen.sleep(1000)
        return True
    return False


def _资源点(ctx: TaskContext, 模板: str, roi: tuple[int, int, int, int]) -> bool:
    """旧节点 ``ancient`` / ``both`` / ``sea`` / ``cantonese`` / ``often``。

    五章都是在缩略地图上的某个 roi 里找 ``resource/0X.png`` 然后点它，
    只有图和 roi 不同 —— 所以合成一个带参数的函数。
    """
    return ctx.tap(IMG(模板, roi=roi, desc=f"选资源点 {模板}"))


def _隐藏面板(ctx: TaskContext) -> bool:
    """旧节点 ``hide_one`` / ``hide_two`` / ``hide_three`` / ``hide_four`` /
    ``hide_five``：点 ``resource/03.png`` 收起地图面板。"""
    return ctx.tap(IMG("resource/03.png", roi=(42, 608, 28, 37), desc="收起地图面板"))


def _滑动(ctx: TaskContext, 起点: tuple[int, int], 终点: tuple[int, int], 延时: int) -> bool:
    """旧节点 ``Swipe1`` ~ ``Swipe8``：地图拖动。

    ``begin`` / ``end`` 都是 ``[x, y, 0, 0]``（绝对坐标），
    其中 ``Swipe3``/``Swipe4``/``Swipe5``/``Swipe6``/``Swipe7``/``Swipe8`` 带 ``post_delay``。
    """
    return ctx.screen.swipe(起点, 终点, delay=延时, desc="拖动地图")


#: 每章的滑动序列（原样照抄旧 JSON 的 begin/end/post_delay）。
#: 一章要挪三次才够到资源点，三章要多滑一次，其余一章一次。
滑动表 = {
    "第一章": (
        ((856, 330), (200, 485), 0),    # Swipe1
        ((995, 315), (500, 445), 0),    # Swipe2
        ((830, 293), (335, 405), 2000),  # Swipe3
    ),
    "第二章": (((265, 355), (965, 390), 2000),),  # Swipe4
    "第三章": (
        ((795, 590), (795, 130), 2000),  # Swipe5
        ((110, 350), (1110, 350), 2000),  # Swipe6
    ),
    "第四章": (((275, 375), (730, 300), 2000),),  # Swipe7
    "第五章": (((1115, 255), (475, 275), 2000),),  # Swipe8
}

#: 每章的「城市名 / 资源点模板 / 资源点 roi」，对应旧 JSON 里那条城市专属链。
#: 值是 ``(城市名, 资源点模板, 资源点 roi)``，``城市名`` 为 None 表示跳过该节点
#: （旧 JSON 里没这个节点）。
章节表 = {
    "第一章": ("来古", "resource/02.png", (126, 598, 41, 81)),    # come_ancient / ancient
    "第二章": ("汴都", "resource/04.png", (242, 598, 38, 83)),    # Biandu / both
    "第三章": ("申海", "resource/05.png", (357, 598, 42, 82)),    # deut_sea / sea
    "第四章": ("粤州", "resource/06.png", (471, 595, 42, 86)),    # cantonese_prefecture / cantonese
    "第五章": ("常安", "resource/07.png", (584, 597, 45, 83)),    # often_quiet / often
}


def 走章节链(ctx: TaskContext, 章: str) -> bool:
    """旧 ``resource_one`` / ``resource_two`` / ``resource_three`` /
    ``resource_four`` / ``resource_five`` 那五条链，合成一个带参数的函数。

    旧 next 是 ``[execute_X, 城市名, big_map_X, 资源点, 两个异常处理]`` ——
    「执行」也好「大地图」也好，谁先命中就走谁的后续；这里写成顺序调用：
    点得动执行就点，点不动就直接点大地图（大地图是备选路径）。
    """
    城市名, 模板, roi = 章节表.get(章, 章节表["第一章"])

    ctx.step(f"进入{章}")
    # 旧 resource_X 的第一个候选是 execute_X；这一下也顺手把列表滚到本章。
    _执行(ctx)
    # 旧 come_ancient / Biandu / ... 只是认城市名，认不到就等下一个候选。
    ctx.scan(
        lambda c: _城市名(c, 城市名),
        _大地图,
        handle_exceptions,
        timeout=20_000,
        desc=f"{章}：找城市/大地图",
    )

    if not ctx.retry(
        lambda: _资源点(ctx, 模板, roi), timeout=20_000, desc=f"{章}：选资源点"
    ):
        return False
    _隐藏面板(ctx)

    for 起点, 终点, 延时 in 滑动表.get(章, 滑动表["第一章"]):
        ctx.check_cancel()
        _滑动(ctx, 起点, 终点, 延时)

    # 旧每章链的最后一步都是 next: [resource]，也就是回到资源列表点「资源」。
    return ctx.tap(OCR("资源", desc="回到资源列表"))


# --------------------------------------------------------------------- 选第几关


def 选关卡(ctx: TaskContext, 关卡名: str) -> bool:
    """旧节点 ``ancient_both_sea_cantonese_often1`` /
    ``ancient_both_sea_cantonese_often2`` / ``ancient_both_sea_cantonese_often3`` /
    ``ancient_both_sea_cantonese_often4`` / ``ancient_both_sea_cantonese_often5``。

    五个节点的差别只有识别哪个数字（壹/贰/叁/肆/伍），点到就接 ``fast``。
    """
    数字 = {
        "第一关（壹）（资源用）": "壹",
        "第二关（贰）（资源用）": "贰",
        "第三关（叁）（资源用）": "叁",
        "第四关（肆）（资源用）": "肆",
        "第五关（伍）（资源用）": "伍",
    }.get(关卡名, "壹")
    return ctx.tap(OCR(数字, desc=f"选第{数字}个资源点"))


# --------------------------------------------------------------------- 打法分流


def 打一次(ctx: TaskContext) -> bool:
    """``选择战斗次数`` = 打一次（速通没解锁）时的分支（旧 ``Start1``）。"""
    if not 点开始(ctx):
        return False
    return 重打直到成功(ctx)


def 按次数速通(ctx: TaskContext, 次数: int) -> bool:
    """按 ``选择战斗次数`` 打固定轮数：1 次走 ``Speedrun1x``，其余走多倍链。"""
    for index in range(次数):
        ctx.check_cancel()
        ctx.step(f"速通第 {index + 1}/{次数} 轮")
        ok = 速通一次(ctx) if 次数 == 1 else 多倍速通(ctx, 次数)
        if not ok:
            return False
    return True


def 全部体力(ctx: TaskContext) -> bool:
    """旧 ``allin`` → ``allin-fast`` 的自循环：速通按钮点不到就说明体力见底。"""
    for _ in range(99):
        ctx.check_cancel()
        ctx.screen.sleep(2000)  # 旧 allin-fast 的 pre_delay: 2000
        if not ctx.tap(
            OCR(
                "速通",
                point=(1030, 660),
                delay=2000,  # 旧 allin-fast 的 post_delay: 2000
                desc="继续速通",
            )
        ):
            return 点活力不足收尾(ctx)
        if not 多倍一次(ctx):
            return 点活力不足收尾(ctx)
    return True


#: 「选择战斗次数」的战斗 case → 对应打法（两个活动专用 case 不在此表内）。
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
    "资源",
    group="战斗",
    order=210,
    options=(哪章, 哪个关卡, 三次次数选项),
    description="进资源 → 选章节 → 拖地图选资源点 → 选第几关 → 按选的次数打",
)
def 资源(ctx: TaskContext) -> bool:
    """旧任务入口 ``resource_all``。

    旧 ``resource_all`` 的 next 是五个 ``resource_X`` 加两个异常处理，靠
    ``选择关卡-资源`` 覆盖 next 来「选中」其中一章；这里直接读选项查 ``章节表``。
    打完之后的选第几关同理（旧 ``resource`` 节点被 ``打哪个-资源`` 覆盖）。
    """
    ctx.step("打开资源")
    # 旧 resource_all：五章是并列候选，异常处理挂在同一条 next 上。
    章 = ctx.text("选择关卡-资源", 哪章.default)
    if 章 not in 章节表:
        ctx.log.warning("不认识的资源章节：%s", 章)
        return False
    if not ctx.scan(
        lambda c: 走章节链(c, 章),
        handle_exceptions,
        timeout=60_000,
        desc=f"打开{章}的资源",
    ):
        ctx.log.warning("没能进入 %s 的资源界面", 章)
        return False

    # 旧节点 resource + ancient_both_sea_cantonese_often1~5：选第几个资源点。
    关卡 = ctx.text("打哪个-资源", 哪个关卡.default)
    ctx.step(f"选资源点：{关卡}")
    if not ctx.retry(lambda: 选关卡(ctx, 关卡), timeout=20_000, desc=f"选 {关卡}"):
        return False

    # 旧节点 fast：这里原本也是「按 option 覆盖 next 选打几倍」，改成查表。
    次数 = ctx.text("选择战斗次数", 三次次数选项.default)
    执行 = 打法.get(次数)
    if 执行 is None:
        ctx.log.warning(
            "「%s」是良宵百载活动专用的次数选项，资源用不了，任务放弃", 次数
        )
        return False
    ctx.step(f"战斗次数：{次数}")
    if not 执行(ctx):
        return False

    ctx.step("资源结束")
    return True
