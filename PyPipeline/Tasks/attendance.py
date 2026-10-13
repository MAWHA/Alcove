"""活动签到：打开活动页 → 进「栖光游灵」→ 把签到奖励领掉。

移植自旧流水线 ``assets/resource_picli/base/pipeline/13_activity_attendance.json``
（8 个节点，见 ``docs/迁移对照表.md`` 第 36 行）。旧图里只有 ``activity`` 一个节点
把 ``next`` 指回自己（反复点「活动」直到签到页出来），这里用 ``ctx.scan`` 表达，
不递归。
"""

from __future__ import annotations

from MWATools.MWATask import OCR, QUIT, TaskContext, handle_exceptions, task


@task(
    "活动签到",
    group="活动",
    order=310,
    description="进活动页，把「栖光游灵」的签到奖励领掉",
)
def 活动签到(ctx: TaskContext) -> bool:
    """旧节点 ``activity_attendance``（entry）。"""
    ctx.step("活动签到")
    # 旧 next：[activity, attendance, [JumpBack]Exception-handling-remind,
    #          [JumpBack]Exception-handling-nurturance-one]
    # 后两项是满世界塞的干扰弹窗，用 MWATools 的共用件 handle_exceptions 代。
    return bool(
        ctx.scan(进活动页, 领栖光游灵, handle_exceptions, timeout=60_000, desc="活动签到")
    )


def 进活动页(ctx: TaskContext) -> bool:
    """旧节点 ``activity``：点左侧「活动」入口。"""
    if not ctx.tap(OCR("活动", roi=(0, 327, 188, 178), delay=2000, desc="打开活动页")):
        return False
    # 旧 next：[attendance, activity, activity-swap]（第二项是它自己 —— 由外层 scan 再扫一轮表达）
    return bool(
        ctx.scan(领栖光游灵, 点一下活动页, handle_exceptions, timeout=20_000, desc="等签到页")
    )


def 点一下活动页(ctx: TaskContext) -> bool:
    """旧节点 ``activity-swap``：无识别、无坐标的 DirectHit。

    旧节点只有 ``action: Click``，既没有 ``roi`` 也没有 ``target``，在 maa 里就是
    「在屏幕上随便点一下」（识别框缺省覆盖全屏，点它的中心）。这里点屏幕中心。
    """
    return ctx.screen.click(desc="在活动页中间点一下")


def 领栖光游灵(ctx: TaskContext) -> bool:
    """旧节点 ``attendance``：点左侧「栖光游灵」进签到页。"""
    if not ctx.tap(OCR("栖光游灵", roi=(0, 0, 255, 717), delay=2000, desc="进「栖光游灵」")):
        return False
    # 旧 next：[attendance_two, attendance_three, Quit]
    return bool(
        ctx.scan(领签到一, 领签到二, QUIT, timeout=30_000, desc="领签到奖励")
    )


def 领签到一(ctx: TaskContext) -> bool:
    """旧节点 ``attendance_two``：点签到格子上的红点（模板 ``activity/01.png``）。

    旧节点带 ``green_mask: true``、``index: -1``（多命中里取最后一个）和
    ``target_offset: [135, -145, 0, 0]``。``Cand`` 表达不了 ``green_mask`` /
    ``index``，所以这一步直接用 ``screen.find`` + ``screen.click``。
    """
    match = ctx.screen.find(
        "activity/01.png", roi=(265, 520, 1015, 200), green_mask=True, index=-1
    )
    if not match:
        return False
    ctx.screen.click(match, offset=(135, -145, 0, 0), delay=3000, desc="点签到红点")
    # 旧 next：[activity_get, Quit]
    return bool(ctx.scan(收下物资, QUIT, timeout=30_000, desc="收下签到奖励"))


def 领签到二(ctx: TaskContext) -> bool:
    """旧节点 ``attendance_three``：OCR「天」（签到页的「第 X 天」）。"""
    if not ctx.tap(OCR("天", delay=3000, desc="点签到格子")):
        return False
    # 旧 next：[activity_get, activity_attendance_two, Quit]
    return bool(
        ctx.scan(收下物资, 打工巧, QUIT, timeout=30_000, desc="收下签到奖励")
    )


def 打工巧(ctx: TaskContext) -> bool:
    """旧节点 ``activity_attendance_two``：OCR「工巧新途」（签到页里的另一个入口）。"""
    if not ctx.tap(OCR("工巧新途", roi=(0, 0, 255, 717), delay=2000, desc="切到「工巧新途」")):
        return False
    # 旧 next：[attendance_two, activity_attendance_two, Quit]（第二项是它自己 —— 由外层负责）
    return bool(ctx.scan(领签到一, QUIT, timeout=20_000, desc="领签到奖励"))


def 收下物资(ctx: TaskContext) -> bool:
    """旧节点 ``activity_get``：OCR「获得物资」。"""
    if not ctx.tap(OCR("获得物资", roi=(930, 70, 310, 570), desc="收下物资")):
        return False
    # 旧 next：[activity_attendance_two, Quit]
    return bool(ctx.scan(打工巧, QUIT, timeout=20_000, desc="继续签到"))
