"""武器制造：进派遣公司 → 装备 → 高级/绝密订单 → 签订合同 → 确定 → 回主界面。

移植自旧流水线 ``3_(9)_weapons_fabricate.json``（16 个节点）。

旧图是「高级」和「绝密」两轮几乎一模一样的流程各写一遍（``signed-contract``
vs ``signed-contract-two``、``weapons-fabricate-determine`` vs
``...-three``、``...-quit`` vs ``...-quit-two``、``...-lack`` vs
``...-lack-two``），只有失败后的去向略有不同：高级单缺材料会转去绝密单，
绝密单缺材料就直接回主界面。这里用一个参数化的循环表达，两轮复用同一段代码。
另外三个 ``-lack`` / ``-full`` 节点是 ``DoNothing`` + ``post_delay: 2000`` ——
识别到异常提示后只是等 2 秒给弹窗时间，不点任何东西。
"""

from __future__ import annotations

from MWATools.MWATask import IMG, OCR, TaskContext, task

# ---------------------------------------------------------------- 常量

#: ``entry_dispath_nine`` —— 「派遣公司」入口。
按钮_派遣公司 = IMG("Company/d_company.png", delay=7000, desc="派遣公司")

#: ``weapons-fabricate-job`` —— 左侧的「装备」。
按钮_装备 = OCR("装备", roi=(0, 155, 160, 160), delay=2000, desc="装备")

#: ``senior-orders`` —— 「高级」订单；旧节点带 target_offset [50,30,0,0]。
按钮_高级订单 = OCR("高级", offset=(50, 30, 0, 0), delay=2000, desc="高级订单")

#: ``confidential-orders`` —— 「绝密」订单；同样带 target_offset [50,30,0,0]。
按钮_绝密订单 = OCR("绝密", offset=(50, 30, 0, 0), delay=2000, desc="绝密订单")

#: ``signed-contract`` / ``signed-contract-two`` —— 「签订合同」。
按钮_签订合同 = OCR("签订合同", roi=(835, 500, 400, 210), delay=2000, desc="签订合同")

#: ``weapons-fabricate-determine`` / ``-three`` —— 「确定」。
按钮_确定 = OCR("确定", roi=(655, 400, 260, 150), delay=2000, desc="确定")

#: ``weapons-fabricate-quit`` —— 「等待生产」，点的是右上角死坐标 (1150, 70)。
按钮_等待生产 = OCR("等待生产", point=(1150, 70), delay=2000, desc="等待生产")

#: ``weapons-fabricate-quit-Image`` —— 右上角那个关闭/返回图标（``Company\29.png``）。
按钮_关闭生产面板 = IMG(
    "Company/29.png", roi=(1050, 0, 200, 190), point=(1150, 70), delay=2000, desc="关闭生产面板"
)

#: ``weapons-fabricate-lack`` / ``-lack-two`` —— 「缺少所需」提示（只等不点）。
文案_缺少所需 = OCR("缺少所需", delay=2000)

#: ``weapons-fabricate-full`` —— 「已满」提示（只等不点）。
文案_制造已满 = OCR("已满", delay=2000)

#: ``weapons-fabricate-home`` —— 主界面标记（``Startup\10.png``）。
按钮_回主界面 = IMG("Startup/10.png", desc="回主界面")


@task(
    "武器制造",
    group="养成",
    order=170,
    description="在装备页签下把高级、绝密订单都排上制造",
)
def 武器制造(ctx: TaskContext) -> bool:
    """旧节点 ``weapons-fabricate``：整条链的入口。"""
    ctx.step("武器制造")
    # 旧 next：[entry_dispath_nine, weapons-fabricate-job, senior-orders]
    return bool(
        ctx.scan(
            进派遣公司,
            点装备页,
            点高级订单,
            timeout=60_000,
            desc="武器制造",
        )
    )


def 进派遣公司(ctx: TaskContext) -> bool:
    """旧节点 ``entry_dispath_nine``。"""
    if not ctx.tap(按钮_派遣公司):
        return False
    # 旧 next：[weapons-fabricate-job, senior-orders, entry_dispath_nine]
    return bool(ctx.scan(点装备页, 点高级订单, timeout=30_000, desc="派遣公司"))


def 点装备页(ctx: TaskContext) -> bool:
    """旧节点 ``weapons-fabricate-job``。"""
    if not ctx.tap(按钮_装备):
        return False
    # 旧 next：[senior-orders, weapons-fabricate-job]
    return bool(ctx.scan(点高级订单, timeout=20_000, desc="装备页"))


def 点高级订单(ctx: TaskContext) -> bool:
    """旧节点 ``senior-orders``：两轮制造的起点（高级单 → 绝密单）。

    旧 ``next`` 是 ``[signed-contract, weapons-fabricate-lack, senior-orders]``，
    识别不到就再点一次自己。这里把它拆成「点高级单 → 走一轮 → 再走一轮绝密单」。
    """
    if not ctx.tap(按钮_高级订单):
        return False
    # 旧 next：[signed-contract, weapons-fabricate-lack]（识别不到时自重试交回上层 scan）
    return bool(_制造一轮(ctx, 绝密=False))


def _制造一轮(ctx: TaskContext, *, 绝密: bool) -> bool:
    """一轮「签合同 → 确定 → 等待生产」；失败时高级单退到绝密单、绝密单退到回主界面。

    旧图这套流程写了两遍（高级：``signed-contract`` / ``-determine`` / ``-quit``
    / ``-lack``；绝密：``signed-contract-two`` / ``-determine-three`` /
    ``-quit-two`` / ``-lack-two``），差别只有失败后的去向，所以用参数收拢。
    """
    合同 = _点签订合同_高级 if not 绝密 else _点签订合同_绝密
    if not 合同(ctx):
        return False
    确认 = _点确定_高级 if not 绝密 else _点确定_绝密
    if not 确认(ctx):
        return False
    收尾 = _点等待生产_高级 if not 绝密 else _点等待生产_绝密
    return bool(收尾(ctx))


def _点签订合同_高级(ctx: TaskContext) -> bool:
    """旧节点 ``signed-contract``。"""
    if not ctx.tap(按钮_签订合同):
        return False
    # 旧 next：[weapons-fabricate-lack, weapons-fabricate-determine, signed-contract]
    return bool(ctx.scan(缺材料_转绝密, _点确定_高级, timeout=20_000, desc="签合同"))


def _点签订合同_绝密(ctx: TaskContext) -> bool:
    """旧节点 ``signed-contract-two``。"""
    if not ctx.tap(按钮_签订合同):
        return False
    # 旧 next：[weapons-fabricate-lack-two, weapons-fabricate-determine-three, signed-contract-two]
    return bool(ctx.scan(缺材料_回主界面, _点确定_绝密, timeout=20_000, desc="签合同"))


def _点确定_高级(ctx: TaskContext) -> bool:
    """旧节点 ``weapons-fabricate-determine``。"""
    if not ctx.tap(按钮_确定):
        return False
    # 旧 next：[weapons-fabricate-lack, weapons-fabricate-quit, weapons-fabricate-full]
    return bool(
        ctx.scan(缺材料_转绝密, _点等待生产_高级, 制造已满, timeout=20_000, desc="确定")
    )


def _点确定_绝密(ctx: TaskContext) -> bool:
    """旧节点 ``weapons-fabricate-determine-three``。"""
    if not ctx.tap(按钮_确定):
        return False
    # 旧 next：[weapons-fabricate-lack-two, weapons-fabricate-quit-two, weapons-fabricate-full]
    return bool(
        ctx.scan(缺材料_回主界面, _点等待生产_绝密, 制造已满, timeout=20_000, desc="确定")
    )


def _点等待生产_高级(ctx: TaskContext) -> bool:
    """旧节点 ``weapons-fabricate-quit``：排上队后收掉右上角面板，转去绝密单。"""
    if not ctx.tap(按钮_等待生产):
        return False
    # 旧 next：[weapons-fabricate-quit-Image, confidential-orders]
    return bool(
        ctx.scan(
            关闭生产面板,
            点绝密订单,
            timeout=20_000,
            desc="等待生产",
        )
    )


def _点等待生产_绝密(ctx: TaskContext) -> bool:
    """旧节点 ``weapons-fabricate-quit-two``：绝密单排完直接回主界面。"""
    if not ctx.tap(按钮_等待生产):
        return False
    # 旧 next：[weapons-fabricate-home]
    return bool(ctx.scan(点回主界面, timeout=20_000, desc="等待生产"))


def 关闭生产面板(ctx: TaskContext) -> bool:
    """旧节点 ``weapons-fabricate-quit-Image``。"""
    if not ctx.tap(按钮_关闭生产面板):
        return False
    # 旧 next：[confidential-orders, weapons-fabricate-quit-Image]
    return bool(ctx.scan(点绝密订单, timeout=20_000, desc="关闭生产面板"))


def 点绝密订单(ctx: TaskContext) -> bool:
    """旧节点 ``confidential-orders``：接力做第二轮（绝密单）。"""
    if not ctx.tap(按钮_绝密订单):
        return False
    # 旧 next：[signed-contract-two, weapons-fabricate-lack-two, weapons-fabricate-quit-Image, confidential-orders]
    return bool(
        ctx.scan(
            _点签订合同_绝密,
            缺材料_回主界面,
            关闭生产面板,
            timeout=20_000,
            desc="绝密订单",
        )
    )


def 缺材料_转绝密(ctx: TaskContext) -> bool:
    """旧节点 ``weapons-fabricate-lack``：材料不够，等 2 秒后改做绝密单。"""
    if not ctx.look(文案_缺少所需):
        return False
    ctx.step("高级订单材料不足，转绝密订单")
    # 旧节点是 DoNothing + post_delay 2000，只是给弹窗留时间。
    ctx.screen.sleep(2000)
    # 旧 next：[confidential-orders]
    return bool(ctx.scan(点绝密订单, timeout=20_000, desc="材料不足"))


def 缺材料_回主界面(ctx: TaskContext) -> bool:
    """旧节点 ``weapons-fabricate-lack-two``：连绝密单也缺材料，收工回主界面。"""
    if not ctx.look(文案_缺少所需):
        return False
    ctx.step("绝密订单材料不足，结束")
    ctx.screen.sleep(2000)
    # 旧 next：[weapons-fabricate-home]
    return bool(ctx.scan(点回主界面, timeout=20_000, desc="材料不足收工"))


def 制造已满(ctx: TaskContext) -> bool:
    """旧节点 ``weapons-fabricate-full``：制造位已满，等 2 秒后回主界面。

    旧图 ``weapons-fabricate-full`` 的 ``next`` 是 ``[weapons-fabricate-home]``。
    """
    if not ctx.look(文案_制造已满):
        return False
    ctx.step("制造位已满")
    ctx.screen.sleep(2000)
    # 旧 next：[weapons-fabricate-home]
    return bool(ctx.scan(点回主界面, timeout=20_000, desc="制造位已满"))


def 点回主界面(ctx: TaskContext) -> bool:
    """旧节点 ``weapons-fabricate-home``（旧图终点）。"""
    return ctx.tap(按钮_回主界面)
