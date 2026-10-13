"""给好友点赞：联系人 → 好友 → 挨个拜访点赞（默认前 4 个）。

移植自旧流水线 ``assets/resource_picli/base/pipeline/15_visit.json``（31 个节点，
见 ``docs/迁移对照表.md`` 第 38 行）。旧图把同一套流程复制了四份（``-one`` /
``-two`` / ``-three`` / ``-four``），差别只有好友列表里的坐标和「拜访」按钮的 roi ——
规范要的是可读的控制流而不是把 JSON 换个语法再写一遍，所以这里用一张坐标表 + 一个
循环表达，每一步的注释里都留着对应的旧节点名，方便逐节点回退核对。
"""

from __future__ import annotations

from MWATools.MWATask import IMG, OCR, TaskContext, handle_exceptions, task

#: 旧 ``visit-Thumbs-up-*``：好友名片上的点赞按钮（``visit/01.png``，``post_delay`` 2000）。
点赞按钮 = IMG("visit/01.png", roi=(260, 610, 110, 110), delay=2000, desc="点赞")

#: 旧 ``visit-friends-all-*``：左侧「好友」分栏（``post_delay`` 1500），四份一模一样。
好友分栏 = OCR("好友", roi=(30, 185, 260, 200), delay=1500, desc="打开好友列表")

#: 四个好友位。字段 = (序号, 好友列表点击 y, 「拜访」按钮 roi, 拜访是否点死坐标)
#: 对应旧节点 ``visit-friends-one``..``four`` 与 ``visit-one``..``four``：
#:   one  (105,365) roi(280,460,75,60)    two  (105,450) roi(280,500,80,80)
#:   three(105,535) roi(280,600,75,60)    four (105,620) —— ``visit-four`` 是 DirectHit，
#: 直接点死坐标 (318,708)，那张 roi 在旧节点里其实不起作用。
好友位 = (
    ("一", 365, (280, 460, 75, 60), False),
    ("二", 450, (280, 500, 80, 80), False),
    ("三", 535, (280, 600, 75, 60), False),
    ("四", 620, (280, 460, 75, 60), True),
)


@task(
    "给好友点赞（目前默认就前4个）",
    group="日常",
    order=70,
    description="联系人 → 好友 → 挨个拜访点赞（默认前 4 个）",
)
def 给好友点赞(ctx: TaskContext) -> bool:
    """旧节点 ``visit``（entry）。

    旧 ``next``：``[visit-contact, visit-friends-all-one, visit-friends-one,
    visit-quit-one, [JumpBack]Exception-handling-remind,
    [JumpBack]Exception-handling-nurturance-one]``。它允许「已经停在好友列表 /
    好友名片上」时从中间进场 —— 这里由 ``打开好友列表`` 与 ``点赞一轮`` 的第一步覆盖。
    """
    ctx.step("给好友点赞（前 4 个）")
    return bool(
        ctx.scan(进联系人, 打开好友列表, handle_exceptions, timeout=120_000, desc="给好友点赞")
    )


def 进联系人(ctx: TaskContext) -> bool:
    """旧节点 ``visit-contact``：点底部「联系人」。"""
    if not ctx.tap(OCR("联系人", roi=(150, 600, 110, 115), delay=1500, desc="打开联系人")):
        return False
    return 打开好友列表(ctx)  # 旧 next：[visit-friends-all-one]


def 打开好友列表(ctx: TaskContext) -> bool:
    """旧节点 ``visit-friends-all-one`` / ``-two`` / ``-three`` / ``-four``（四份一模一样）。"""
    if not ctx.tap(好友分栏):
        return False
    return 点赞一轮(ctx)  # 旧 next：[visit-friends-one]（其余三份同理）


def 点赞一轮(ctx: TaskContext) -> bool:
    """旧节点 ``visit-friends-one``..``four`` 一直到 ``visit-quit-four`` 的整串流程。

    ``visit-quit-N`` 的 ``next`` 又指回 ``visit-friends-all-(N+1)``，也就是
    「关掉名片 → 重新打开好友列表 → 点下一个坑位」——四份复制品合成一个循环。
    """
    for index, (序号, y, 拜访roi, 直接点) in enumerate(好友位):
        ctx.check_cancel()
        if index:  # 旧 visit-quit-{one,two,three} 的 next 都是 visit-friends-all-{two,three,four}
            if not ctx.tap(好友分栏):
                return False
        if not 点好友位(ctx, 序号, y):
            return False
        if not 点拜访(ctx, 序号, 拜访roi, 直接点):
            return False
        if not 点赞(ctx, 序号):
            return False
    # 旧 visit-quit-four 的 next：[visit-quit] —— 最后一次关闭，post_delay 2000
    return 关掉面板(ctx, delay=2000, desc="收尾：关掉好友名片")


def 点好友位(ctx: TaskContext, 序号: str, y: int) -> bool:
    """旧节点 ``visit-friends-one`` / ``-two`` / ``-three`` / ``-four``。

    旧节点没有识别（DirectHit），直接点好友列表里的死坐标 ``(105, y)``，``post_delay`` 750。
    旧 ``next``：``-one`` 是 ``[visit-one, visit-friends-one]``；``-two`` / ``-three``
    多一个 ``visit-quit`` 兜底；``-four`` 是 ``[visit-four, visit-friends-four]``。
    自己那一项由 ``点赞一轮`` 的循环与 ``点拜访`` 失败后的重试表达。
    """
    return ctx.screen.click((105, y), delay=750, desc=f"点第{序号}个好友")


def 点拜访(ctx: TaskContext, 序号: str, roi: tuple[int, int, int, int], 直接点: bool) -> bool:
    """旧节点 ``visit-one`` / ``-two`` / ``-three`` / ``-four``。

    前三个是 OCR「拜访」（roi 各不相同）＋ ``target_offset: [0,-30,0,0]``
    （点识别框上方 30px），``post_delay`` 7000；``visit-four`` 是 DirectHit，
    直接点死坐标 ``(318,708)``。
    """
    if 直接点:
        return ctx.screen.click((318, 708), delay=7000, desc=f"拜访第{序号}个好友")
    return ctx.tap(
        OCR("拜访", roi=roi, offset=(0, -30, 0, 0), delay=7000, desc=f"拜访第{序号}个好友")
    )


def 点赞(ctx: TaskContext, 序号: str) -> bool:
    """旧节点 ``visit-Thumbs-up-*`` → ``visit-get-*`` / ``visit-on-get-*`` → ``visit-quit-*``。"""
    if not ctx.tap(点赞按钮):  # 旧 visit-Thumbs-up-N（next：[visit-get-N, visit-on-get-N]）
        return False
    for _ in range(20):
        ctx.check_cancel()
        # 旧 visit-get-N：点「得」收下本周的赞（next 里含自己 → 循环收完）
        if ctx.tap(OCR("得", delay=2000, desc="收下本周的赞")):
            continue
        # 旧 visit-on-get-N：看到「本周」说明已经赞过，DoNothing + post_delay 2000
        if ctx.look(OCR("本周")):
            ctx.screen.sleep(2000)
            break
        break
    # 旧 visit-get-N / visit-on-get-N 的 next 都是 visit-quit-N（post_delay 7000）
    return 关掉面板(ctx, delay=7000, desc=f"关掉第{序号}个好友的名片")


def 关掉面板(ctx: TaskContext, *, delay: int, desc: str = "关掉当前面板") -> bool:
    """旧节点 ``visit-quit-one``/``-two``/``-three``/``-four``（7000）与 ``visit-quit``（2000）。

    ``MWATools`` 的共用件 ``QUIT`` 识别的是同一张 ``Collect/06.png``，但它不带
    ``post_delay``；这里每次的延时都不一样，所以按旧节点原样带上。
    """
    return ctx.tap(IMG("Collect/06.png", delay=delay, desc=desc))
