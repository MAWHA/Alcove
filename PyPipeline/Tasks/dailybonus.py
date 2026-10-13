"""每日免费礼包：主界面 → 商亭 → 礼包 → 循时 → 免费的那一档 → 购买。

移植自旧流水线 ``4_dailybonus.json``（7 个节点）。整条链是一路「点进去、等一下、
再点下一层」，每一层的 ``next`` 都写着「找不到下一步就回头重点自己」——
在 Python 里就是 ``ctx.scan(下一步, 自己, ...)``。
"""

from __future__ import annotations

from MWATools.MWATask import OCR, QUIT, TaskContext, handle_exceptions, task

# ---------------------------------------------------------------- 常量

#: ``shangting`` —— 主界面上的「商亭」入口。
按钮_商亭 = OCR("商亭", delay=2000, desc="商亭")

#: ``libao`` —— 商亭里的「礼包」页签。
页签_礼包 = OCR("礼包", delay=2000, desc="礼包")

#: ``richang`` —— 「循时」分类。
分类_循时 = OCR("循时", delay=2000, desc="循时")

#: ``donggu`` —— 免费的那一档。
档位_免费 = OCR("免费", delay=2000, desc="免费礼包")

#: ``goumai`` —— 「购买」按钮。
按钮_购买 = OCR("购买", delay=2000, desc="购买")

#: ``obtain1`` —— 「获得物资」结算弹窗。
按钮_获得物资 = OCR("获得物资", delay=2000, desc="获得物资")


@task(
    "每日免费礼包",
    group="日常",
    order=30,
    description="从主界面进商亭，把循时分类里的免费礼包买掉",
)
def 每日免费礼包(ctx: TaskContext) -> bool:
    """旧节点 ``business_kiosk``：整条链的入口。

    旧 ``next`` 是 ``[shangting, libao, richang, donggu, Quit, Exception-*]`` ——
    「哪一层没点完就从哪一层接着点」，所以整条链被打包成一个入口函数由 ``scan``
    反复调。
    """
    ctx.step("每日免费礼包")
    return bool(
        ctx.scan(
            进商亭,
            点礼包页,
            点循时,
            点免费档位,
            QUIT,
            handle_exceptions,
            timeout=60_000,
            desc="领每日免费礼包",
        )
    )


def 进商亭(ctx: TaskContext) -> bool:
    """旧节点 ``shangting``。"""
    if not ctx.tap(按钮_商亭):
        return False
    # 旧 next：[libao, shangting]
    return bool(ctx.scan(点礼包页, 进商亭, timeout=20_000, desc="进商亭"))


def 点礼包页(ctx: TaskContext) -> bool:
    """旧节点 ``libao``。"""
    if not ctx.tap(页签_礼包):
        return False
    # 旧 next：[richang, libao]
    return bool(ctx.scan(点循时, 点礼包页, timeout=20_000, desc="切到礼包页"))


def 点循时(ctx: TaskContext) -> bool:
    """旧节点 ``richang``。"""
    if not ctx.tap(分类_循时):
        return False
    # 旧 next：[donggu, Quit]
    return bool(ctx.scan(点免费档位, QUIT, timeout=20_000, desc="选循时"))


def 点免费档位(ctx: TaskContext) -> bool:
    """旧节点 ``donggu``：选中免费档，然后点购买。"""
    if not ctx.tap(档位_免费):
        return False
    # 旧 next：[goumai, donggu, Quit]
    return bool(ctx.scan(点购买, 点免费档位, QUIT, timeout=20_000, desc="选免费档"))


def 点购买(ctx: TaskContext) -> bool:
    """旧节点 ``goumai``：点「购买」买下免费礼包。"""
    if not ctx.tap(按钮_购买):
        return False
    # 旧 next：[obtain1, donggu]
    return bool(ctx.scan(领物资, 点免费档位, timeout=20_000, desc="购买"))


def 领物资(ctx: TaskContext) -> bool:
    """旧节点 ``obtain1``：把「获得物资」的结算点掉收工。

    旧节点带 ``pre_wait_freezes: 1000`` —— 结算弹窗弹出前先等画面静止 1 秒，
    对应这里的 ``ctx.screen.wait_freezes``。
    """
    ctx.screen.wait_freezes(time=1000)
    if not ctx.tap(按钮_获得物资):
        return False
    # 旧 next：[Quit, obtain1]
    return bool(ctx.scan(QUIT, 领物资, timeout=20_000, desc="收下礼包"))
