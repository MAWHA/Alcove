"""领取家具蓝图：进派遣公司 → 茶室 → 蓝图 → 反复点「领取」直到领完。

移植自旧流水线 ``3_(8)blueprint.json``（6 个节点）。

旧图 ``blueprint-one`` 之后的 ``blueprint-Receive`` ⇄ ``blueprint-get`` 是一对
互为 ``next`` 的节点 —— 「领取」点一下出现「得」（确认），确认完又回到「领取」，
直到屏幕上没有可以领的为止。旧图靠两个节点互相指来绕圈，这里写成一个
``while`` 循环，读起来就是它实际干的事：能领就再领一次。
"""

from __future__ import annotations

from MWATools.MWATask import IMG, OCR, TaskContext, handle_exceptions, task

# ---------------------------------------------------------------- 常量

#: ``entry_dispath_eight`` —— 「派遣公司」入口。
按钮_派遣公司 = IMG("Company/d_company.png", delay=7000, desc="派遣公司")

#: ``blueprint-tearoom`` —— 「茶室」。
按钮_茶室 = OCR("茶室", roi=(965, 365, 155, 295), delay=2000, desc="茶室")

#: ``blueprint-one`` —— 顶部的「蓝图」页签。
页签_蓝图 = OCR("蓝图", roi=(880, 10, 400, 160), delay=2000, desc="蓝图")

#: ``blueprint-Receive`` —— 「取」按钮（识别 roi 与死坐标 target 不同，target 才是点击点）。
按钮_领取 = OCR("取", roi=(1160, 130, 120, 275), point=(1200, 185), delay=2000, desc="领取蓝图")

#: ``blueprint-get`` —— 确认弹窗上的「得」。
按钮_确认领取 = OCR("得", delay=2000, desc="确认领取")

#: ``combine-home`` —— 主界面标记（``Startup\10.png``，两处 ``next`` 都指向它）。
按钮_回主界面 = IMG("Startup/10.png", desc="回主界面")


@task(
    "领取家具蓝图",
    group="养成",
    order=160,
    description="去茶室把能领的家具蓝图全领了",
)
def 领取家具蓝图(ctx: TaskContext) -> bool:
    """旧节点 ``blueprint-all``：整条链的入口。"""
    ctx.step("领取家具蓝图")
    # 旧 next：[entry_dispath_eight, blueprint-tearoom, blueprint-one, 2×Exception]
    return bool(
        ctx.scan(
            进派遣公司,
            点茶室,
            点蓝图页,
            handle_exceptions,
            timeout=60_000,
            desc="领取家具蓝图",
        )
    )


def 进派遣公司(ctx: TaskContext) -> bool:
    """旧节点 ``entry_dispath_eight``。"""
    if not ctx.tap(按钮_派遣公司):
        return False
    # 旧 next：[blueprint-tearoom, blueprint-one, 2×Exception]
    return bool(
        ctx.scan(点茶室, 点蓝图页, handle_exceptions, timeout=30_000, desc="派遣公司")
    )


def 点茶室(ctx: TaskContext) -> bool:
    """旧节点 ``blueprint-tearoom``。"""
    if not ctx.tap(按钮_茶室):
        return False
    # 旧 next：[blueprint-one]
    return bool(ctx.scan(点蓝图页, timeout=20_000, desc="茶室"))


def 点蓝图页(ctx: TaskContext) -> bool:
    """旧节点 ``blueprint-one``。"""
    if not ctx.tap(页签_蓝图):
        return False
    # 旧 next：[blueprint-Receive, combine-home]
    return bool(ctx.scan(领取蓝图, 点回主界面, timeout=30_000, desc="蓝图页"))


def 领取蓝图(ctx: TaskContext) -> bool:
    """旧节点 ``blueprint-Receive`` ⇄ ``blueprint-get``：反复领直到没有可领的。

    旧图这两个节点的 ``next`` 里都带着对方和 ``combine-home``：
    点「取」→ 出现「得」→ 点「得」→ 回到「取」。只要还能识别到「取」就一直领，
    识别不到就回主界面收工。
    """
    if not ctx.tap(按钮_领取):
        return False
    while ctx.tap(按钮_确认领取):
        ctx.step("继续领取蓝图")
    # 旧 next：[combine-home]（两个节点都指向它）
    return bool(ctx.scan(点回主界面, timeout=20_000, desc="领完蓝图"))


def 点回主界面(ctx: TaskContext) -> bool:
    """旧节点 ``combine-home``（旧图终点）。"""
    return ctx.tap(按钮_回主界面)
