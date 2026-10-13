"""领取日常（含游历）：把每日/周常任务与游历奖励一键领了。

移植自旧流水线 ``9receive_reward.json``（10 个节点）。

旧图的两个坑：
1. 入口 ``task1`` 是个空节点，把 ``daily1``/``weekly1``/``travel1``/``mission1``
   全塞进 ``next`` 里，靠「谁先命中走谁」来选入口 —— 实质是「这几个入口哪个
   在屏幕上就点哪个」。
2. 领取按钮点完之后不会立刻回主界面，而是会被 ``Quit1`` 拉去 ``travel1``
   再走一遍，所以这里也保留了「领完 → 回主界面 → 再扫游历」的绕法。
"""

from __future__ import annotations

from MWATools.MWATask import IMG, OCR, TaskContext, handle_exceptions, task

# ---------------------------------------------------------------- 常量

#: ``daily1`` —— 右下角的「任务」页签。
页签_任务 = OCR("任务", roi=(1149, 650, 74, 40), delay=2000, desc="任务页签")

#: ``all1`` —— 面板底部的「全部领取」。
按钮_全部领取 = OCR("全部领取", roi=(0, 575, 1280, 150), delay=5000, desc="全部领取")

#: ``material1`` —— 「获得物资」结算弹窗。
按钮_获得物资 = OCR("获得物资", delay=3000, desc="获得物资")

#: ``weekly1`` —— 左侧的「周常」分类。
页签_周常 = OCR("周常", roi=(80, 310, 100, 98), delay=2000, desc="周常")

#: ``travel1`` —— 右下角的「游历」入口。
按钮_游历 = OCR("游历", roi=(773, 656, 60, 36), delay=3000, desc="游历")

#: ``mission1`` —— 左侧的「任务」分类（与 ``页签_任务`` 的 roi 不同，别合并）。
页签_任务分类 = OCR("任务", roi=(0, 230, 195, 195), delay=2000, desc="任务分类")

#: ``challenge`` —— 「挑战」分类。
页签_挑战 = OCR("挑战", delay=2000, desc="挑战")

#: ``reward1`` —— 「奖励」页签。
页签_奖励 = OCR("奖励", roi=(23, 134, 97, 81), delay=2000, desc="奖励")

#: ``Quit1`` —— 关闭当前领取面板。
按钮_关闭面板 = IMG("receive_reward/01.png", delay=5000, desc="关闭领取面板")


@task(
    "领取日常(包括游历)",
    group="日常",
    order=65,
    description="领取每日/周常任务奖励，并顺手把游历奖励领了",
)
def 领取日常(ctx: TaskContext) -> bool:
    """旧节点 ``task1``：整条链的入口。"""
    ctx.step("领取日常")
    # 旧 next：[daily1, weekly1, travel1, mission1, Exception-remind, Exception-nurturance-one]
    return bool(
        ctx.scan(
            点任务页签,
            点周常页签,
            点游历,
            点任务分类,
            handle_exceptions,
            timeout=40_000,
            desc="领取日常",
        )
    )


def 点任务页签(ctx: TaskContext) -> bool:
    """旧节点 ``daily1``。"""
    if not ctx.tap(页签_任务):
        return False
    # 旧 next：[all1, weekly1, Quit1]
    return bool(ctx.scan(点全部领取, 点周常页签, 关闭面板, timeout=30_000, desc="日常页"))


def 点全部领取(ctx: TaskContext) -> bool:
    """旧节点 ``all1``。"""
    if not ctx.tap(按钮_全部领取):
        return False
    # 旧 next：[material1, weekly1, mission1, challenge, reward1]
    return bool(
        ctx.scan(
            点获得物资,
            点周常页签,
            点任务分类,
            点挑战页签,
            点奖励页签,
            timeout=30_000,
            desc="全部领取",
        )
    )


def 点获得物资(ctx: TaskContext) -> bool:
    """旧节点 ``material1``。"""
    if not ctx.tap(按钮_获得物资):
        return False
    # 旧 next：[all1, weekly1, mission1, reward1, Quit]
    return bool(
        ctx.scan(
            点全部领取,
            点周常页签,
            点任务分类,
            点奖励页签,
            关闭面板,
            timeout=30_000,
            desc="获得物资",
        )
    )


def 点周常页签(ctx: TaskContext) -> bool:
    """旧节点 ``weekly1``。"""
    if not ctx.tap(页签_周常):
        return False
    # 旧 next：[all1, material1, Quit1]
    return bool(ctx.scan(点全部领取, 点获得物资, 关闭面板, timeout=30_000, desc="周常页"))


def 点游历(ctx: TaskContext) -> bool:
    """旧节点 ``travel1``：游历界面的奖励也要领。"""
    if not ctx.tap(按钮_游历):
        return False
    # 旧 next：[mission1, challenge, reward1, all1]
    return bool(
        ctx.scan(点任务分类, 点挑战页签, 点奖励页签, 点全部领取, timeout=30_000, desc="游历")
    )


def 点任务分类(ctx: TaskContext) -> bool:
    """旧节点 ``mission1``。"""
    if not ctx.tap(页签_任务分类):
        return False
    # 旧 next：[all1, challenge, reward1, Quit]
    return bool(
        ctx.scan(点全部领取, 点挑战页签, 点奖励页签, 关闭面板, timeout=30_000, desc="任务分类")
    )


def 点挑战页签(ctx: TaskContext) -> bool:
    """旧节点 ``challenge``。"""
    if not ctx.tap(页签_挑战):
        return False
    # 旧 next：[all1, reward1]
    return bool(ctx.scan(点全部领取, 点奖励页签, timeout=30_000, desc="挑战"))


def 点奖励页签(ctx: TaskContext) -> bool:
    """旧节点 ``reward1``。"""
    if not ctx.tap(页签_奖励):
        return False
    # 旧 next：[all1, Quit]
    return bool(ctx.scan(点全部领取, 关闭面板, timeout=30_000, desc="奖励"))


def 关闭面板(ctx: TaskContext) -> bool:
    """旧节点 ``Quit1``：关掉面板后旧图会绕去 ``travel1`` 再走一轮。"""
    if not ctx.tap(按钮_关闭面板):
        return False
    # 旧 next：[travel1, Exception-remind, Exception-nurturance-one]
    ctx.screen.sleep(5000)
    return bool(ctx.scan(点游历, handle_exceptions, timeout=20_000, desc="回主界面"))
