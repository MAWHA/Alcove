"""邮箱：打开邮箱，把「全部领取」点掉，然后一件件收附件。

移植自旧流水线 ``10receivemail.json``（节点 ``Mail`` / ``EnterMail`` /
``ReceiveMail`` / ``Mail-get``）。每个旧节点在这里都还能找到对应的一小段代码，
注释里留着原名，方便对着 JSON 回退核对。
"""

from __future__ import annotations

from MWATools.MWATask import IMG, OCR, QUIT, TaskContext, handle_exceptions, task

#: 主页上的邮箱图标。``Mail`` 节点以前是靠 ``EnterMail`` 里的模板匹配找到它的。
MAIL_ICON = IMG("Mainpage/mail.png", desc="主页邮箱图标")


@task(
    "邮箱",
    group="日常",
    order=60,
    description="打开邮箱 → 全部领取 → 把剩下的附件一个个收掉",
)
def 邮箱(ctx: TaskContext) -> bool:
    """旧节点 ``Mail``。

    ``next`` 是 ``[EnterMail, [JumpBack]Exception-handling-*]``，翻译过来就是
    「反复试着打开邮箱，中间顺手把登录提示之类的弹窗关掉」。
    """
    ctx.step("打开邮箱")
    # 30 秒内如果连邮箱图标都点不到，说明不在这套界面里，交给上层判断。
    return bool(ctx.scan(进邮箱, handle_exceptions, timeout=30_000, desc="打开邮箱"))


def 进邮箱(ctx: TaskContext) -> bool:
    """旧节点 ``EnterMail``：点主页的邮箱图标，然后等邮箱界面起来。"""
    if not ctx.tap(MAIL_ICON):
        return False
    # 旧 next：[ReceiveMail, Quit, [JumpBack]Exception-handling-*]
    return bool(
        ctx.scan(领全部, QUIT, handle_exceptions, timeout=20_000, desc="等邮箱打开")
    )


def 领全部(ctx: TaskContext) -> bool:
    """旧节点 ``ReceiveMail``：点「全部领取」。"""
    if not ctx.tap(OCR("全部", delay=5000, desc="全部领取")):
        return False
    # 旧 next：[Mail-get, Quit]
    return bool(ctx.scan(收附件, QUIT, timeout=30_000, desc="收附件"))


def 收附件(ctx: TaskContext) -> bool:
    """旧节点 ``Mail-get``：点「得」收下一件附件。

    旧 ``next`` 是 ``[Quit, Mail-get]`` —— 先看有没有关闭按钮，没有就再点一次
    「得」。这里写成一个循环，语义一样但不会递归。
    """
    while True:
        ctx.check_cancel()
        if not ctx.tap(OCR("得", delay=2000, desc="收下一件附件")):
            return False
        if ctx.tap(QUIT):
            return True
