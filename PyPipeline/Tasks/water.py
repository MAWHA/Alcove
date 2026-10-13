"""体力水：点主界面的体力条 → 看还剩多少天 → 该喝的喝掉。

移植自两条旧流水线：``6_drink_a_2day_water.json``（2 个节点）和
``6_(02)water.json``（8 个节点）。任务名就是它干的事 ——
**「在主界面喝完（/上限）支持剩余1天，一天以内的水一并喝了）」**：
体力药剂有「剩余 2 天 / 1 天」之分，快过期的（2 天和 1 天）一并喝掉，
喝到提示「上限」为止。

旧图的写法是「``drink`` 节点把 ``huipo`` / ``water`` / ``max_water`` /
``drink_a_2day_water`` 全列在 ``next`` 里，谁命中走谁」，这么列有两个后果：
一读不出意图，二每次都要重头认一遍。这里改成直白的分支。
"""

from __future__ import annotations

from MWATools.MWATask import IMG, OCR, TaskContext, handle_exceptions, task

# ---------------------------------------------------------------- 常量

#: ``drink_a_2day_water`` —— 主界面右上角的体力条。
按钮_体力条 = IMG("Mainpage/stamina.png", roi=(1188, 259, 67, 66), delay=1000, desc="体力条")

#: ``Swipe_drink`` —— 把药剂列表往下拖，好看到快过期的那几瓶。
#: 旧 action 是 ``Swipe``，begin/end 就是这两个点。
起点_拖列表 = (400, 245)
终点_拖列表 = (400, 445)

#: ``huipo`` —— 「剩余购买次数」说明条。
文案_剩余购买次数 = OCR("剩余购买次数", roi=(280, 485, 218, 52), delay=0, desc="剩余购买次数")

#: ``huipo`` 点的是叉（死坐标），不是文字本身。
按钮_关闭说明 = (615, 75)

#: ``water`` —— 药剂页签。
页签_药剂 = OCR("药剂", roi=(244, 132, 130, 36), desc="药剂")

#: ``sub_2daywater`` —— 药瓶上的「2天 / 1天 / 时」字样（阈值调高，避免认错）。
文案_天数 = OCR(
    ["2天", "1天", "时"],
    roi=(390, 120, 160, 140),
    threshold=0.85,
    offset=(-10, 35, 0, 0),
    desc="选中快过期的药剂",
)

#: ``sub_drink`` —— 确认喝掉（复用 Collect/04.png 那个勾）。
按钮_确认喝 = IMG("Collect/04.png", delay=3000, desc="确认喝掉")

#: ``quit_fork`` —— 退出药剂面板的叉。
按钮_退出面板 = IMG("dst/fork.png", desc="退出药剂面板")

#: ``max_water`` —— 喝到上限了（死坐标的「知道了」）。
文案_上限 = OCR("上限", point=(170, 400), desc="体力已达上限")

#: ``click_water`` —— 上限提示上的「知道了」（死坐标）。
按钮_知道了 = (170, 400)


@task(
    "在主界面喝完（/上限）支持剩余1天，一天以内的水一并喝了）",
    group="日常",
    order=50,
    description="打开体力药剂面板，把剩余 1~2 天的体力水喝到上限",
)
def 喝体力水(ctx: TaskContext) -> bool:
    """旧节点 ``drink_a_2day_water``：从主界面点开体力条。

    旧 ``next`` 是 ``[max_water, Swipe_drink, drink, Exception-*]``：点开之后
    可能直接看到「上限」，也可能要先往下拖一拖才看得到快过期的药。
    """
    ctx.step("打开体力药剂面板")
    if not ctx.tap(按钮_体力条):
        return False
    # 旧 next：[max_water, Swipe_drink, drink, Exception-remind, Exception-nurturance-one]
    return bool(
        ctx.scan(
            上限提示,
            拖动列表,
            喝药剂,
            handle_exceptions,
            timeout=30_000,
            desc="打开体力面板",
        )
    )


def 拖动列表(ctx: TaskContext) -> bool:
    """旧节点 ``Swipe_drink``：把药剂列表往上拖一屏。"""
    ctx.screen.swipe(起点_拖列表, 终点_拖列表, duration=300, desc="拖动药剂列表")
    # 旧 next：[drink]
    return bool(ctx.scan(喝药剂, timeout=15_000, desc="拖动后继续"))


def 喝药剂(ctx: TaskContext) -> bool:
    """旧节点 ``drink``：药剂面板上的主循环。

    旧 ``next`` 是 ``[huipo, water, max_water, drink_a_2day_water]``：先看有没有
    「剩余购买次数」说明、再切到药剂页、（喝完了就）看上限提示、最后退回体力条。
    这里按同样的优先级扫一遍，谁命中走谁。
    """
    return bool(
        ctx.scan(
            点剩余购买次数,
            点药剂页,
            上限提示,
            回到体力条,
            timeout=30_000,
            desc="喝药剂",
        )
    )


def 点剩余购买次数(ctx: TaskContext) -> bool:
    """旧节点 ``huipo``：点掉「剩余购买次数」说明条上的叉。"""
    if not ctx.look(文案_剩余购买次数):
        return False
    ctx.screen.click(按钮_关闭说明, desc="关掉剩余购买次数提示")
    # 旧 next 是字符串 "quit_fork"，即直接退面板。
    return bool(ctx.scan(退出面板, timeout=15_000, desc="退出药剂面板"))


def 点药剂页(ctx: TaskContext) -> bool:
    """旧节点 ``water``：切到「药剂」页，然后挑快过期的。"""
    if not ctx.tap(页签_药剂):
        return False
    # 旧 next：[sub_2daywater, quit_fork]
    return bool(ctx.scan(选天数药剂, 退出面板, timeout=20_000, desc="药剂页"))


def 选天数药剂(ctx: TaskContext) -> bool:
    """旧节点 ``sub_2daywater``：挑中「剩余 2 天 / 1 天」的那瓶。

    旧节点的识别带了 ``target_offset: [-10, 35, 0, 0]``，也就是点识别框偏左下的
    位置（药瓶本体），已挂在 ``文案_天数`` 的 ``offset`` 上。
    """
    if not ctx.tap(文案_天数):
        return False
    # 旧 next：[max_water, sub_drink, quit_fork, click_water]
    return bool(
        ctx.scan(上限提示, 确认喝掉, 退出面板, 点知道了, timeout=30_000, desc="选药剂")
    )


def 确认喝掉(ctx: TaskContext) -> bool:
    """旧节点 ``sub_drink``：确认对话框上的勾。"""
    if not ctx.tap(按钮_确认喝):
        return False
    # 旧 next：[max_water, drink_a_2day_water, quit_fork]
    return bool(
        ctx.scan(上限提示, 回到体力条, 退出面板, timeout=30_000, desc="确认喝掉")
    )


def 上限提示(ctx: TaskContext) -> bool:
    """旧节点 ``max_water``：喝到上限了。

    旧节点认到「上限」后往死坐标 ``(170, 400)`` 点一下「知道了」，因为是死坐标，
    所以这里认一次、点一次即可（点完没有后续节点）。
    """
    if not ctx.look(文案_上限):
        return False
    ctx.step("体力已达上限")
    ctx.screen.click(按钮_知道了, desc="知道了")
    return True


def 点知道了(ctx: TaskContext) -> bool:
    """旧节点 ``click_water``：直接点上限提示上的「知道了」（不识别）。"""
    ctx.screen.click(按钮_知道了, desc="知道了")
    return True


def 退出面板(ctx: TaskContext) -> bool:
    """旧节点 ``quit_fork``：点叉关掉药剂面板。"""
    return ctx.tap(按钮_退出面板)


def 回到体力条(ctx: TaskContext) -> bool:
    """旧节点 ``drink_a_2day_water``（在 ``drink`` 的 ``next`` 里被复用）。

    循环到这一步说明这一次已经点完了（没到上限），那就重新点一次体力条 ——
    旧图也是这么绕回去的。**只点体力条**，剩下的交给上层的主循环继续扫，
    这样不会递归，喝几瓶就迭代几次。
    """
    if not ctx.tap(按钮_体力条):
        return False
    return bool(ctx.scan(喝药剂, timeout=20_000, desc="再喝一轮"))
