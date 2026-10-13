"""和合：进派遣公司 → 茶室 → 和合 → 挑版本 → 开一局 → 转一圈 → 退出 → 回主界面。

移植自旧流水线 ``3_(7)combine.json``（25 个节点）。

旧图的写法（也是这次移植最需要拆掉的地方）：
``combine-choose`` 是个**空节点**，它自己不干任何事，只是把六条路列在 ``next``
里（``combine-chair-entry`` / ``combine-dynasty-entry`` / ``combine-ship-entry``
以及三条已经进过界面的 ``combine-chair`` / ``combine-dynasty`` / ``combine-ship``），
真正决定走哪条的是 interface.json 里的 ``和合版本`` option —— 它把
``combine-choose`` 的 ``next`` 覆写成单一分支。也就是说「选版本」是靠改 ``next``
实现的，图里根本读不出意图。

这里不绕这个圈：直接 ``ctx.text("和合版本")`` 读选项，查表决定分支；
三条分支重复的「进公司 / 点茶室 / 点玩法」抽成一个共用的步骤序列。
"""

from __future__ import annotations

from MWATools.MWATask import (
    Choice,
    IMG,
    OCR,
    Option,
    TaskContext,
    handle_exceptions,
    task,
)

# ---------------------------------------------------------------- 常量

#: ``entry_dispath_seven`` 等三条链的第一步 —— 「派遣公司」入口。
按钮_派遣公司 = IMG("Company/d_company.png", delay=7000, desc="派遣公司")

#: ``tearoom-combine`` 等 —— 「茶室」。
按钮_茶室 = OCR("茶室", roi=(965, 365, 155, 295), delay=2000, desc="茶室")

#: ``combine-one`` 等 —— 和合玩法图标（``Company\28.png``）。
按钮_和合玩法 = IMG("Company/28.png", roi=(210, 110, 180, 200), delay=2000, desc="和合玩法")

#: ``combine-chair`` / ``combine-dynasty`` / ``combine-ship`` 的识别目标。
文案_椅 = OCR("椅", desc="和合·椅")
文案_朝代 = OCR("朝代", desc="和合·朝代")
文案_船 = OCR("船", desc="和合·船")

#: ``combine-game`` —— 「开始游戏」。
按钮_开始游戏 = OCR("开始游戏", delay=2000, desc="开始游戏")

#: ``combine-challenge`` —— 局内的「退出」。
按钮_退出 = OCR("退出", delay=1000, desc="退出和合")

#: ``combine-return`` —— 结算面板上的返回箭头。
按钮_返回 = IMG("Company/return.png", desc="返回")

#: ``combine-home`` —— 主界面标记（``Startup\10.png``）。
按钮_回主界面 = IMG("Startup/10.png", desc="回主界面")

#: option ``和合版本``，case 名逐字抄自 interface.json；未写 default_case，取第一个。
和合版本 = Option(
    "和合版本",
    label="和合版本",
    kind="select",
    default="和合·椅",
    choices=(
        Choice("和合·椅"),
        Choice("和合·朝代"),
        Choice("和合·船"),
    ),
    description="选择要做哪一种和合",
)


# ---------------------------------------------------------------- 分支链

def _进和合界面(ctx: TaskContext, 选版本) -> bool:
    """三条版本链共用的「进公司 → 茶室 → 玩法 → 选版本」序列。

    旧图里这三步在三条链上各写了一遍（``entry_dispath_seven`` →
    ``tearoom-combine`` → ``combine-one`` 和它们的 chair/dynasty/ship 版本），
    反复的 ``next`` 自重试一模一样，所以合成一个序列跑。
    """
    if not ctx.tap(按钮_派遣公司):
        return False
    if not ctx.tap(按钮_茶室):
        return False
    if not ctx.tap(按钮_和合玩法):
        return False
    return bool(选版本(ctx))


def _和合椅链(ctx: TaskContext) -> bool:
    """旧节点 ``combine-chair-entry`` → ``combine-chair-tearoom`` → ``combine-chair-combine`` → ``combine-chair``。"""
    return _进和合界面(ctx, _选椅)


def _和合朝代链(ctx: TaskContext) -> bool:
    """旧节点 ``combine-dynasty-entry`` → ``combine-dynasty-tearoom`` → ``combine-dynasty-combine`` → ``combine-dynasty``。"""
    return _进和合界面(ctx, _选朝代)


def _和合船链(ctx: TaskContext) -> bool:
    """旧节点 ``combine-ship-entry`` → ``combine-ship-tearoom`` → ``combine-ship-combine`` → ``combine-ship``。"""
    return _进和合界面(ctx, _选船)


# case 名 → 分支链（替代旧图靠 pipeline_override 改 ``combine-choose`` 的 next）。
# 之所以放在文件末尾用 ``update`` 填，是因为这些分支函数要先定义好。
_版本分支: dict = {}


@task(
    "和合",
    group="养成",
    order=150,
    options=(和合版本,),
    description="进茶室做一次和合，版本由「和合版本」选项决定",
)
def 和合(ctx: TaskContext) -> bool:
    """旧节点 ``combine-all``：整条链的入口。"""
    ctx.step("和合")
    # 旧 next：[entry_dispath_seven, tearoom-combine, combine-one, combine-choose, combine-game, 2×Exception]
    return bool(
        ctx.scan(
            进派遣公司,
            点茶室,
            点玩法,
            选和合,
            开始游戏,
            handle_exceptions,
            timeout=60_000,
            desc="和合",
        )
    )


def 进派遣公司(ctx: TaskContext) -> bool:
    """旧节点 ``entry_dispath_seven``。"""
    if not ctx.tap(按钮_派遣公司):
        return False
    # 旧 next：[tearoom-combine, combine-one, combine-game, 2×Exception]
    return bool(
        ctx.scan(点茶室, 点玩法, 开始游戏, handle_exceptions, timeout=30_000, desc="派遣公司")
    )


def 点茶室(ctx: TaskContext) -> bool:
    """旧节点 ``tearoom-combine``。"""
    if not ctx.tap(按钮_茶室):
        return False
    # 旧 next：[combine-one, combine-game]
    return bool(ctx.scan(点玩法, 开始游戏, timeout=20_000, desc="茶室"))


def 点玩法(ctx: TaskContext) -> bool:
    """旧节点 ``combine-one``。"""
    if not ctx.tap(按钮_和合玩法):
        return False
    # 旧 next：[combine-choose]
    return bool(ctx.scan(选和合, timeout=20_000, desc="和合玩法"))


def 选和合(ctx: TaskContext) -> bool:
    """旧节点 ``combine-choose``（空节点，靠 option 覆盖 next 选分支）。

    这里换成读选项 + 查表。
    """
    版本 = ctx.text("和合版本", "和合·椅")
    分支 = _版本分支.get(版本)
    if 分支 is None:
        ctx.step(f"未知的和合版本：{版本}")
        return False
    return bool(分支(ctx))


def _选椅(ctx: TaskContext) -> bool:
    """旧节点 ``combine-chair``。"""
    if not ctx.tap(文案_椅):
        return False
    # 旧 next：[combine-game]
    return bool(ctx.scan(开始游戏, timeout=20_000, desc="选了椅"))


def _选朝代(ctx: TaskContext) -> bool:
    """旧节点 ``combine-dynasty``。"""
    if not ctx.tap(文案_朝代):
        return False
    # 旧 next：[combine-game]
    return bool(ctx.scan(开始游戏, timeout=20_000, desc="选了朝代"))


def _选船(ctx: TaskContext) -> bool:
    """旧节点 ``combine-ship``。"""
    if not ctx.tap(文案_船):
        return False
    # 旧 next：[combine-game]
    return bool(ctx.scan(开始游戏, timeout=20_000, desc="选了船"))


def 开始游戏(ctx: TaskContext) -> bool:
    """旧节点 ``combine-game``。"""
    if not ctx.tap(按钮_开始游戏):
        return False
    # 旧 next：[combine-challenge, combine-swiping-one]
    return bool(ctx.scan(退出和合, 滑动一, timeout=30_000, desc="开始游戏"))


# ---------------------------------------------------------------- 局内绕圈

def 滑动一(ctx: TaskContext) -> bool:
    """旧节点 ``combine-swiping-one``。"""
    ctx.screen.swipe((850, 180), (850, 450), delay=1000, desc="和合滑一")
    # 旧 next：[combine-challenge, combine-swiping-two]
    return bool(ctx.scan(退出和合, 滑动二, timeout=20_000, desc="滑一"))


def 滑动二(ctx: TaskContext) -> bool:
    """旧节点 ``combine-swiping-two``。"""
    ctx.screen.swipe((850, 450), (570, 450), delay=1000, desc="和合滑二")
    # 旧 next：[combine-challenge, combine-swiping-three]
    return bool(ctx.scan(退出和合, 滑动三, timeout=20_000, desc="滑二"))


def 滑动三(ctx: TaskContext) -> bool:
    """旧节点 ``combine-swiping-three``。"""
    ctx.screen.swipe((570, 450), (570, 180), delay=1000, desc="和合滑三")
    # 旧 next：[combine-challenge, combine-swiping-four]
    return bool(ctx.scan(退出和合, 滑动四, timeout=20_000, desc="滑三"))


def 滑动四(ctx: TaskContext) -> bool:
    """旧节点 ``combine-swiping-four``。"""
    ctx.screen.swipe((570, 180), (850, 180), delay=1000, desc="和合滑四")
    # 旧 next：[combine-challenge, combine-swiping-one] —— 一圈滑完又从头开始
    return bool(ctx.scan(退出和合, 滑动一, timeout=20_000, desc="滑四"))


def 退出和合(ctx: TaskContext) -> bool:
    """旧节点 ``combine-challenge``：点「退出」，然后一路回主界面。"""
    if not ctx.tap(按钮_退出):
        return False
    # 旧 next：[combine-return, combine-challenge]
    return bool(ctx.scan(点返回, timeout=20_000, desc="退出和合"))


def 点返回(ctx: TaskContext) -> bool:
    """旧节点 ``combine-return``。"""
    if not ctx.tap(按钮_返回):
        return False
    # 旧 next：[combine-home]
    return bool(ctx.scan(点回主界面, timeout=20_000, desc="返回"))


def 点回主界面(ctx: TaskContext) -> bool:
    """旧节点 ``combine-home``（旧图终点）。"""
    return ctx.tap(按钮_回主界面)


_版本分支.update(
    {
        "和合·椅": _和合椅链,
        "和合·朝代": _和合朝代链,
        "和合·船": _和合船链,
    }
)
