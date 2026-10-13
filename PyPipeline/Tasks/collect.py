"""器者征集：进征集界面 → 收掉已完成的队列 → 开一轮新的征集 → 领结果。

移植自旧流水线 ``2_collect_operators.json``（24 个节点）。旧图里最绕的一段是
``Collect-add-all`` —— 它自己什么都不做，只靠 interface.json 里 ``征集几个``
这个 option 覆盖它的 ``next`` 来挑「加 1 个 / 2 个 / 3 个 / 4 个」。在 Python
里这层绕圈没必要：直接读选项、查表调对应的分支函数。

另外旧 JSON 里到处塞的 ``[JumpBack]Exception-handling-*``
（``-convened`` / ``-quit`` / ``-home`` / ``-Network reconnection`` / ``-remind``
/ ``-nurturance-one``）就是共用的 ``handle_exceptions``，不再重复实现。
"""

from __future__ import annotations

from MWATools.MWATask import (
    Choice,
    IMG,
    OCR,
    Option,
    QUIT,
    TaskContext,
    handle_exceptions,
    task,
)

# ---------------------------------------------------------------- 常量

#: ``Collecting-operators`` —— 征集界面的入口按钮。
按钮_器者征集 = OCR("器者征集", delay=2000, desc="器者征集")

#: ``Collect-ReceiveOperators`` —— 「领取」已攒好的器者。
按钮_领取 = IMG("Collect/02.png", delay=2000, desc="领取器者")

#: ``Collect-ReceiveCollect`` / ``Collect-new-role`` —— 弹出层上的「全部」。
按钮_全部 = OCR("全部", delay=1000, desc="全部")

#: ``Collect-changan`` —— 长按「全部」3 秒把奖励一次性吸掉（旧 action: Swipe 原地）。
起点_长按 = (645, 635)
终点_长按 = (645, 635)
时长_长按 = 3000

#: ``Collect-Skip`` —— 抽卡动画的「跳过」。
按钮_跳过 = IMG("Collect/05.png", delay=4000, desc="跳过开箱动画")

#: ``Collect-outcome`` —— 「征集结果」标题，点报告中间偏下的位置。
按钮_征集结果 = OCR("征集结果", point=(645, 625), delay=2000, desc="征集结果")

#: ``Collect-get`` —— 「获得物资」。
按钮_获得物资 = OCR("获得物资", delay=2000, desc="获得物资")

#: ``Collect-quit2`` —— 队列里没有已完成项时的提示条（只等，不点）。
文案_无已完成队列 = OCR("当前没有已经完成的征集队列", delay=2000)

#: ``Collect-back`` —— 提示条上的「回去」按钮（死坐标）。
按钮_回去 = (330, 360)

#: ``Collect-Collecting2`` —— 开始征集。
按钮_开始征集 = OCR("开始征集", delay=2000, desc="开始征集")

#: ``Collect-full`` —— 队列已满。
文案_队列已满 = OCR("队列已满", delay=2000)

#: ``Collect-no_solicitation`` —— 缺少道具。
按钮_缺少道具 = OCR("缺少道具", delay=2000, desc="缺少道具")

#: ``Collect-gou`` —— 最后的确认勾。
按钮_确认勾 = IMG("Collect/04.png", delay=2000, desc="确认征集")

#: ``Collect-add-one`` —— 一个都不加，只确认「抽取」那张卡在不在（旧 action: DoNothing）。
卡_抽取 = IMG("Collect/03.png")

#: ``Collect-add-two/three/four`` 每次点这个位置加一个名额（死坐标）。
点_加名额 = (770, 350)

#: ``Collect-repeat-role`` —— 重复器者的确认按钮（只在左侧那一小条里找）。
按钮_重复 = OCR("重复", roi=(0, 230, 300, 210), delay=3000, desc="确认重复器者")


# ---------------------------------------------------------------- 选项

#: 旧 interface.json 的 ``征集几个``：``Collect-add-all`` 的 ``next`` 被它整个覆盖，
#: 于是「空节点选分支」变成了这张查表。
几个 = Option(
    "征集几个",
    label="征集几个",
    kind="select",
    default="征集1个",
    choices=(Choice("征集1个"), Choice("征集2个"), Choice("征集3个"), Choice("征集4个")),
    description="一轮征集同时抽几个",
)

#: case 名 → 旧 JSON 里的分支函数（``Collect-add-one`` ~ ``Collect-add-four``）。
#: 表在文件末尾（四个分支函数定义完之后）填充。
_分支表: dict = {}


@task(
    "器者征集",
    group="抽取",
    order=20,
    options=(几个,),
    description="收掉已完成的征集队列，再按所选个数开一轮新的",
)
def 器者征集(ctx: TaskContext) -> bool:
    """旧节点 ``Collect``：进征集界面。

    旧 ``next`` 是「先试着进征集界面，不行就顺手收掉已完成的队列」，中间夹着一串
    ``[JumpBack]Exception-handling-*``；这里就是「反复扫，直到进得去」。
    开局 ``post_delay`` 5000 也照抄 —— 面板要等动画。
    """
    ctx.step("打开器者征集")
    ctx.screen.sleep(5000)
    return bool(
        ctx.scan(
            进征集界面,
            领器者,
            handle_exceptions,
            timeout=30_000,
            desc="打开器者征集",
        )
    )


# ---------------------------------------------------------------- 逐节点动作


def 进征集界面(ctx: TaskContext) -> bool:
    """旧节点 ``Collecting-operators``。"""
    if not ctx.tap(按钮_器者征集):
        return False
    # 旧 next：[Collect-ReceiveOperators, Collect-ReceiveCollect, 自己, Exception-*]
    return bool(
        ctx.scan(
            领器者,
            领全部物资,
            进征集界面,
            handle_exceptions,
            timeout=30_000,
            desc="等征集界面",
        )
    )


def 领器者(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-ReceiveOperators``：点「领取」，把攒好的器者收下来。"""
    if not ctx.tap(按钮_领取):
        return False
    # 旧 next：[Collect-ReceiveCollect, 自己, Exception-Network reconnection]
    return bool(
        ctx.scan(领全部物资, 领器者, handle_exceptions, timeout=20_000, desc="领取器者")
    )


def 领全部物资(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-ReceiveCollect``：弹出层上点「全部」。"""
    if not ctx.tap(按钮_全部):
        return False
    # 旧 next：[Collect-changan, Collect-quit2, Exception-Network reconnection]
    # 「当前没有已经完成的征集队列」是个前置条件节点（不点），命中就只等 2 秒。
    return bool(
        ctx.scan(长按全部, 无已完成队列, handle_exceptions, timeout=20_000, desc="领取全部")
    )


def 长按全部(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-changan``：在「全部」上原地长按，把奖励一次吸完。"""
    if not ctx.look(OCR("长按")):
        return False
    ctx.screen.swipe(起点_长按, 终点_长按, duration=时长_长按, delay=3000, desc="长按全部")
    # 旧 next：[Collect-Skip]
    return bool(ctx.scan(跳过动画, timeout=20_000, desc="等开箱动画"))


def 跳过动画(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-Skip``：一路点「跳过」，直到出现结果页。"""
    if not ctx.tap(按钮_跳过):
        return False
    # 旧 next：[Collect-outcome, Collect-new-role, Collect-repeat-role, 自己]
    return bool(
        ctx.scan(
            点征集结果,
            领新器者,
            领重复器者,
            跳过动画,
            timeout=60_000,
            desc="等抽卡结果",
        )
    )


def 领新器者(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-new-role``：新器者弹窗上的「全部」。"""
    if not ctx.tap(按钮_全部):
        return False
    # 旧 next：[Collect-quit2, 自己, Collect-back]
    return bool(
        ctx.scan(无已完成队列, 领新器者, 点回去, timeout=20_000, desc="领新器者")
    )


def 领重复器者(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-repeat-role``：重复器者的确认。"""
    if not ctx.tap(按钮_重复):
        return False
    # 旧 next：[Collect-quit2, 自己, Collect-back]
    return bool(
        ctx.scan(无已完成队列, 领重复器者, 点回去, timeout=20_000, desc="领重复器者")
    )


def 无已完成队列(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-quit2``：只是「没有已完成队列」的提示（不点，等 2 秒）。"""
    if not ctx.look(文案_无已完成队列):
        return False
    ctx.screen.sleep(2000)
    # 旧 next：[Collect-back]
    return bool(ctx.scan(点回去, timeout=15_000, desc="点回去"))


def 点回去(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-back``：提示条上的「回去」死坐标。"""
    ctx.screen.click(按钮_回去, desc="回去")
    ctx.screen.sleep(800)  # 旧节点没有 post_delay，给面板一点反应时间
    return True


def 点征集结果(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-outcome``：点「征集结果」，然后一路收「获得物资」。"""
    if not ctx.tap(按钮_征集结果):
        return False
    # 旧 next：[Collect-get, 自己]
    return bool(
        ctx.scan(点获得物资, 点征集结果, timeout=30_000, desc="等征集结果")
    )


def 点获得物资(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-get``：收完物资后回到「开始征集」。"""
    if not ctx.tap(按钮_获得物资):
        return False
    # 旧 next：[Collect-Collecting2, 自己, Collect-back]
    return bool(
        ctx.scan(点开始征集, 点获得物资, 点回去, timeout=30_000, desc="收物资")
    )


def 点开始征集(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-Collecting2``：点「开始征集」，再按队列情况走。"""
    if not ctx.tap(按钮_开始征集):
        return False
    # 旧 next：[Collect-full, Collect-no_solicitation, Collect-add-all]
    return bool(
        ctx.scan(队列已满, 缺少道具, 选征集个数, timeout=30_000, desc="开始征集")
    )


def 队列已满(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-full``：队列满了，关掉面板收工。"""
    if not ctx.look(文案_队列已满):
        return False
    ctx.step("征集队列已满")
    ctx.screen.sleep(2000)
    # 旧 next：[Quit]
    return bool(ctx.scan(QUIT, timeout=10_000, desc="退出征集界面"))


def 缺少道具(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-no_solicitation``：缺道具，点一下提示再退出。"""
    if not ctx.tap(按钮_缺少道具):
        return False
    ctx.step("缺少征集道具")
    # 旧 next：[Quit]
    return bool(ctx.scan(QUIT, timeout=10_000, desc="退出征集界面"))


def 选征集个数(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-add-all``。

    旧写法：这个节点自己 ``post_delay: 2000`` 后什么也不做，``next`` 里列了
    ``Collect-add-one`` ~ ``Collect-add-four`` 四个分支，实际走哪个由 option
    ``征集几个`` 覆盖 ``next`` 决定。这里直接把「覆盖」翻成一次字典查表。
    """
    ctx.screen.sleep(2000)  # 旧节点自己的 post_delay
    case = ctx.text("征集几个", "征集1个")
    if case not in _分支表:
        ctx.log.warning("未知的「征集几个」取值 %r，退回征集1个", case)
        case = "征集1个"
    ctx.step(f"选择抽取个数：{case}")
    return _分支表[case](ctx)


def 加完毕(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-gou``：点上最后的确认勾。"""
    if not ctx.tap(按钮_确认勾):
        return False
    # 旧 next：[Quit]
    return bool(ctx.scan(QUIT, timeout=20_000, desc="退出征集界面"))


# ---------------------------------------------------------------- 分支实现


def _加名额(ctx: TaskContext, *, 个数: str) -> bool:
    """按 ``个数`` 调对应的分支函数（查表）。"""
    return globals()[分支表[个数]](ctx)


def _加一个(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-add-one``：什么都不加，只确认「抽取」那张卡在。

    旧节点是 ``action: DoNothing`` + 模板 ``Collect/03.png``，也就是说「认到了」
    就算这一步做完，然后去点最后的确认勾。
    """
    if not ctx.look(卡_抽取):
        return False
    return 点勾前(ctx)


def _加两个(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-add-two``：点一次「＋」再加两个名额。

    （旧图里一个 ``＋`` 加两个 —— 这是游戏自己的规则，照抄。）
    """
    if not ctx.look(卡_抽取):
        return False
    ctx.screen.click(点_加名额, delay=2000, desc="加名额")
    return 点勾前(ctx)


def _加三个(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-add-three``：点一次「＋」后继续走 ``Collect-jia4``。"""
    if not ctx.look(卡_抽取):
        return False
    ctx.screen.click(点_加名额, desc="加名额")
    return 补点加名额(ctx, 剩几次=1)


def _加四个(ctx: TaskContext) -> bool:
    """旧节点 ``Collect-add-four``：点一次「＋」后继续走 ``Collect-jia3`` → ``jia4``。"""
    if not ctx.look(卡_抽取):
        return False
    ctx.screen.click(点_加名额, desc="加名额")
    return 补点加名额(ctx, 剩几次=2)


def 补点加名额(ctx: TaskContext, *, 剩几次: int) -> bool:
    """旧节点 ``Collect-jia3`` / ``Collect-jia4``：把剩下的「＋」点完。

    这两个节点没有识别，就是直接点死坐标 ``(770, 350)``，所以写成一个小循环
    比抄两遍一模一样的分支函数清楚。
    """
    for _ in range(剩几次):
        ctx.check_cancel()
        ctx.screen.click(点_加名额, desc="加名额")
    return 点勾前(ctx)


def 点勾前(ctx: TaskContext) -> bool:
    """旧 ``Collect-add-one/two/three/four`` 共用的 ``next``。

    ``[Collect-gou, Collect-no_solicitation, Collect-full]`` —— 能点勾就点勾，
    否则可能是缺道具或队列满了。
    """
    return bool(
        ctx.scan(加完毕, 缺少道具, 队列已满, timeout=20_000, desc="确认征集")
    )


_分支表.update(
    {
        "征集1个": _加一个,
        "征集2个": _加两个,
        "征集3个": _加三个,
        "征集4个": _加四个,
    }
)
