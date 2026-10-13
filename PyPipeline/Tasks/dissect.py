"""分解装备：进分解界面 → 选分解到什么品质 → 确认 → 退出。

移植自旧流水线 ``12_dissect_weapon.json``。旧的 ``select_tier`` 是个「啥也不做、
只靠 option 覆盖 next 来选蓝色/红色/黄色」的占位节点 —— 在 Python 里这种绕圈
完全不需要了，直接读选项、查表点对应的坐标即可。
"""

from __future__ import annotations

from MWATools.MWATask import Choice, Option, TaskContext, handle_exceptions, task

#: 旧节点 `red` / `yellow` / `blue` 的点击区域，原样照抄 JSON 里的 ``target``。
#: （maa 里 ``target: [x, y, w, h]`` 点的是这个矩形的中心，我们的
#: ``screen.click((x, y, w, h))`` 语义完全一样，所以不用换算。）
品质坐标 = {
    "炽级": (585, 659, 128, 51),   # 旧节点 red
    "耀级": (464, 664, 118, 39),   # 旧节点 yellow
    "凌级": (339, 663, 124, 41),   # 旧节点 blue
}

#: 旧 interface.json 里 `分解的装备的最大品质` 这个 select，默认取第一个 case。
品质 = Option(
    "分解的装备的最大品质",
    label="分解的装备的最大品质",
    kind="select",
    default="炽级",
    choices=(Choice("炽级"), Choice("耀级"), Choice("凌级")),
    description="只分解到这个品质，更高级的留着",
)


@task(
    "分解装备",
    group="养成",
    order=180,
    options=(品质,),
    description="打开装备分解界面，按所选品质分解一轮",
)
def 分解装备(ctx: TaskContext) -> bool:
    ctx.step("打开分解界面")
    # 旧节点 dissect_weapon：DirectHit，无识别，直接点右下角那一片。
    ctx.screen.click((1002, 647, 107, 50), delay=2000, desc="打开分解界面")

    # 旧节点 dissect_button → select_tier。
    ctx.screen.click((1139, 61, 117, 42), delay=2000, desc="进入装备分解")

    tier = ctx.text("分解的装备的最大品质", "炽级")
    rect = 品质坐标.get(tier, 品质坐标["炽级"])
    ctx.step(f"选择品质：{tier}")
    ctx.screen.click(rect, delay=2000, desc=f"选 {tier}")

    # 旧节点 confirm → center_confirm。
    if not ctx.scan(
        _点确认,
        _点二级确认,
        handle_exceptions,
        timeout=20_000,
        desc="确认分解",
    ):
        ctx.log.warning("没等到确认按钮，可能这一轮没有可分解的装备")
        return False

    ctx.step("退出接收奖励界面")
    # 旧节点 exit01 → exit02，两张图是同一个「领取并退出」的两态。
    ctx.scan(_退出奖励一, _退出奖励二, timeout=15_000, desc="退出奖励界面")
    return True


def _点确认(ctx: TaskContext) -> bool:
    """旧节点 confirm。"""
    return ctx.screen.click((1082, 654, 128, 48), delay=2000, desc="点确认分解")


def _点二级确认(ctx: TaskContext) -> bool:
    """旧节点 center_confirm：弹窗中间的「确定」。"""
    return ctx.screen.click((693, 440, 159, 54), delay=2000, desc="弹窗确定")


def _退出奖励一(ctx: TaskContext) -> bool:
    """旧节点 exit01：模板 receive_reward/01.png。"""
    from MWATools.MWATask import IMG

    return ctx.tap(IMG("receive_reward/01.png", desc="领取并退出（一）"))


def _退出奖励二(ctx: TaskContext) -> bool:
    """旧节点 exit02：模板 receive_reward/02.png。"""
    from MWATools.MWATask import IMG

    return ctx.tap(IMG("receive_reward/02.png", desc="领取并退出（二）"))
