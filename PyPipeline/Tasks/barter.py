"""易物所：进易物所 → 挑一样还能买的 → 选最大数量 → 购买 → 领物资 → 再来一轮。

移植自旧流水线 ``5_Barter.json``（10 个节点）。四个 ``random_*`` 节点是同一张
模板图 ``Shop/01.png`` 在四个不同 roi 里的匹配 —— 也就是「四个货位里哪个还能买」，
所以它们在入口的 ``next`` 里是**并列**的，谁先命中就走谁。
"""

from __future__ import annotations

from MWATools.MWATask import IMG, OCR, QUIT, TaskContext, handle_exceptions, task

# ---------------------------------------------------------------- 常量

#: ``Barter`` —— 主界面上的「易物所」入口。
按钮_易物所 = OCR("易物所", delay=2000, desc="易物所")

#: ``random_one`` ~ ``random_four`` —— 四个货位的可购买标记。
#: 同一张模板图，四个 roi 原样照抄旧 JSON。
货位 = (
    IMG("Shop/01.png", roi=(295, 328, 53, 40), delay=1000, desc="货位一"),
    IMG("Shop/01.png", roi=(523, 328, 51, 42), delay=1000, desc="货位二"),
    IMG("Shop/01.png", roi=(756, 328, 46, 42), delay=1000, desc="货位三"),
    IMG("Shop/01.png", roi=(981, 328, 62, 41), delay=1000, desc="货位四"),
)

#: ``max`` —— 「最大」数量按钮。
按钮_最大 = OCR("最大", desc="最大数量")

#: ``purchase`` —— 「购买」按钮。
按钮_购买 = IMG("Shop/02.png", roi=(570, 447, 54, 51), delay=2000, desc="购买")

#: ``no_money`` —— 「没有足够」的提示；旧节点把 target 写成死坐标 (720, 120)。
按钮_没钱 = OCR("没有足够", point=(720, 120), delay=1000, desc="没钱的提示")

#: ``obtain`` —— 「获得物资」结算弹窗。
按钮_获得物资 = OCR("获得物资", delay=2000, desc="获得物资")


@task(
    "易物所",
    group="日常",
    order=40,
    description="在易物所里把还能买的货位买空一轮",
)
def 易物所(ctx: TaskContext) -> bool:
    """旧节点 ``Barter_random``：整条链的入口。"""
    ctx.step("易物所")
    return bool(
        ctx.scan(
            进易物所,
            逛货位,
            QUIT,
            handle_exceptions,
            timeout=60_000,
            desc="易物所采购",
        )
    )


def 进易物所(ctx: TaskContext) -> bool:
    """旧节点 ``Barter``。"""
    if not ctx.tap(按钮_易物所):
        return False
    # 旧 next：[random_one..four, Quit]
    return bool(ctx.scan(*货位, QUIT, timeout=30_000, desc="进易物所"))


def 逛货位(ctx: TaskContext) -> bool:
    """旧节点 ``random_one`` ~ ``random_four`` 的共同后续。

    旧图里这四步各写了一遍 ``next: [max, Quit]``，其实完全一样，所以这里合成
    一个函数 —— 四张候选（``货位``）谁命中都走它。
    """
    # 旧 next：[max, Quit]
    return bool(ctx.scan(选最大数量, QUIT, timeout=30_000, desc="选货位"))


def 选最大数量(ctx: TaskContext) -> bool:
    """旧节点 ``max``。"""
    if not ctx.tap(按钮_最大):
        return False
    # 旧 next：[purchase, Quit]
    return bool(ctx.scan(点购买, QUIT, timeout=20_000, desc="拉到最大"))


def 点购买(ctx: TaskContext) -> bool:
    """旧节点 ``purchase``。"""
    if not ctx.tap(按钮_购买):
        return False
    # 旧 next：[no_money, obtain, Quit]
    return bool(ctx.scan(点没钱提示, 领物资, QUIT, timeout=30_000, desc="购买"))


def 点没钱提示(ctx: TaskContext) -> bool:
    """旧节点 ``no_money``：钱不够，点掉提示条就收工。"""
    if not ctx.tap(按钮_没钱):
        return False
    ctx.step("易物所余额不足")
    # 旧 next：[Quit]
    return bool(ctx.scan(QUIT, timeout=10_000, desc="退出易物所"))


def 领物资(ctx: TaskContext) -> bool:
    """旧节点 ``obtain``：领完物资后回到货位列表，继续买下一件。

    旧节点带 ``pre_wait_freezes: 2000`` —— 结算弹窗出来前先等画面静止 2 秒。
    """
    ctx.screen.wait_freezes(time=2000)
    if not ctx.tap(按钮_获得物资):
        return False
    # 旧 next：[random_one..four, Quit]
    return bool(ctx.scan(*货位, QUIT, timeout=30_000, desc="领物资"))
