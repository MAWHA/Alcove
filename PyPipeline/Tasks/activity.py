"""良宵百载（活动）：按选项进对应玩法，打关或领奖，战斗失败按选项决定放弃/继续。

移植自旧流水线 ``assets/resource_picli/base/pipeline/14_activity.json``（79 个节点，
见 ``docs/迁移对照表.md`` 第 37 行）。旧图有三处「绕圈」写法，这里都用直白的 Python
表达，注释里留着旧节点名，方便逐节点回退核对：

* ``activity-fine`` / ``activity-lantern`` / 战斗那几步的 ``next`` 里含它们自己
  （靠 maa 的图执行器反复命中）；这里写成 ``ctx.scan`` 循环，逐节点对照但不递归。
* ``activity-fail`` 一个节点的 ``next`` 被 **3 个** option 覆盖，合并后永远由
  「选择是否放弃」决定 —— 这是旧 GUI / MaaPiCli 的实际行为，原样保留，见 ``战斗失败``。
* 「选择进程」的「短途旅游」「赏味」两个 case 覆盖的是 ``activity-hundred``，而这个
  节点在 14_activity.json 和整个 pipeline 目录里**都不存在**（悬空覆盖），所以这两个
  取值实际不改变行为，见 ``展会之后``。

跨文件接缝（规范禁止任务模块互相 import）：

* ``next`` 里的 ``fast`` 定义在 ``7_(03)allin.json``，属于 ``training.py`` 的模块
  （对照表第 28 行）；这里只照抄 ``fast`` 自己那一步，详见 ``速通战斗``。
* ``start-convened`` 是 ``Exception-handling.json`` 里的主界面标记 —— 用 ``MWATools``
  的共用件 ``MAIN_PAGE``（见 ``已在主界面``）。
* ``activity-combustion-two`` .. ``nine``（含各自的 ``*-swipe``）在旧配置里**没有任何
  东西引用**（既不在任何默认 ``next`` 里，也没有 option 覆盖指向它们）—— 是死节点，
  本模块没有实现。

option 的 key / case 名全部从 ``assets/interface.json`` 原样抄来，包括「选择战斗次数」
里那两条带全角括号和「专用！！！」的 case 名，不要改。
"""

from __future__ import annotations

import time

from MWATools.MWATask import (
    IMG,
    MAIN_PAGE,
    OCR,
    Choice,
    Option,
    TaskContext,
    handle_exceptions,
    task,
)

# --------------------------------------------------------------------- 选项
#
# 默认值 = 旧配置里没有 ``default_case`` 时的第一个 case。

选项_进程 = "选择进程（短途旅游、观灯、赏味）"
选项_关卡 = "选择关卡-活动"
选项_次数 = "选择战斗次数"
选项_放弃 = "选择是否放弃(战斗失败时的选择)"

进程选项 = Option(
    选项_进程,
    label=选项_进程,
    kind="select",
    default="短途旅游",
    choices=(Choice("短途旅游"), Choice("璀璨"), Choice("华灯夜"), Choice("赏味")),
    description="去哪一档玩法（「短途旅游」「赏味」在旧配置里是悬空覆盖，见模块说明）",
)

关卡选项 = Option(
    选项_关卡,
    label=选项_关卡,
    kind="select",
    default="第一关",
    choices=(
        Choice("第一关"),
        Choice("第二关"),
        Choice("第三关"),
        Choice("第四关"),
        Choice("第五关"),
        Choice("第六关"),
        Choice("非战斗选项选择这个"),
        Choice("华灯夜选这个"),
    ),
    description="打第几关；后两个 case 是旧配置里的「非战斗」标记，只影响战斗失败的分支",
)

次数选项 = Option(
    选项_次数,
    label=选项_次数,
    kind="select",
    default="打一次（速通没解锁专用）",
    choices=(
        Choice("打一次（速通没解锁专用）"),
        Choice("打一次（速通解锁专用）"),
        Choice("打两次（速通解锁专用）"),
        Choice("打四次（速通解锁专用）"),
        Choice("打十次（速通解锁专用）"),
        Choice("全部体力（速通解锁专用）"),
        Choice("非战斗选项选择这个(活动“良宵百载”专用！！！）"),
        Choice("华灯夜选择这个(活动“良宵百载”专用！！！）"),
    ),
    description="战斗次数（旧配置靠覆盖 fast 节点实现，见 速通战斗）",
)

放弃选项 = Option(
    选项_放弃,
    label=选项_放弃,
    kind="select",
    default="放弃",
    choices=(
        Choice("放弃"),
        Choice("继续"),
        Choice("打璀璨选择这个"),
        Choice("非战斗选项选择这个"),
    ),
    description="战斗失败后是否放弃；这个选项的每个 case 都覆盖 activity-fail，永远由它决定",
)

# --------------------------------------------------------------------- 共用候选项

#: 旧 ``activity-fine``：活动主页上那个「工巧新途」入口（OCR 词表：工巧 / 新途）。
佳期入口 = OCR(["工巧", "新途"], delay=2000, desc="打开「工巧新途」活动页")

#: 旧 ``activity-home`` / ``activity-hundred-home``：左上角回主页的按钮。
#: （旧节点 ``activity-home`` 本身写成下面的函数 ``回主页``，这个候选项是给
#: ``退出活动`` / ``从子界面回主页`` 复用的。）
回主页按钮 = IMG("Startup/10.png", delay=2000, desc="回主页")

#: 旧 ``activity-quit`` / ``activity-journey-quit`` / ``activity-hundred-quit``：
#: 「领取并退出」那个按钮（三个节点用的是同一张 receive_reward/01.png）。
关掉领奖界面 = IMG("receive_reward/01.png", delay=2000, desc="关掉领奖界面")

#: 六个关卡：旧节点名 → (要点掉的数字, 要不要先左滑把关卡挪出来)。
#: 第四~第六关在旧图里都是「``activity-fire-N-swipe`` 左滑 → ``activity-fire-N`` 点数字」两步。
关卡表 = {
    "第一关": ("一", False),
    "第二关": ("二", False),
    "第三关": ("三", False),
    "第四关": ("四", True),
    "第五关": ("五", True),
    "第六关": ("六", True),
}

#: 赏味（筹备）的七道菜：旧节点 ``activity-taste-one`` .. ``seven`` 的 OCR 词与 roi，
#: 顺序就是旧 ``activity-taste`` 的 next 顺序。
赏味七味 = (
    ("琼瑶", (140, 315, 92, 39)),
    ("呈新", (302, 551, 93, 37)),
    ("熙熙", (573, 443, 90, 39)),
    ("鱼龙", (426, 240, 97, 36)),
    ("九宾", (773, 239, 89, 39)),
    ("万年", (894, 496, 86, 38)),
    ("且", (1076, 297, 86, 38)),
)


# --------------------------------------------------------------------- 入口


@task(
    "良宵百载",
    group="活动",
    order=300,
    options=(进程选项, 关卡选项, 次数选项, 放弃选项),
    description="良宵百载：按所选玩法/关卡跑一轮，战斗失败按「选择是否放弃」处理",
)
def 良宵百载(ctx: TaskContext) -> bool:
    """旧节点 ``activity-all``（entry）。"""
    ctx.step(
        f"良宵百载：{ctx.text(选项_进程, '短途旅游')} / {ctx.text(选项_关卡, '第一关')}"
    )
    # 旧 next：[activity-fine, activity-hundred-home, activity-hundred-quit]
    return bool(
        ctx.scan(
            进佳期,
            从子界面回主页,
            关掉领奖弹窗,
            handle_exceptions,
            timeout=60_000,
            desc="打开「良宵百载」",
        )
    )


def 进佳期(ctx: TaskContext) -> bool:
    """旧节点 ``activity-fine``：点开「工巧新途」，再按选项进对应玩法。"""
    if not ctx.tap(佳期入口):
        return False
    # 旧 next：[activity-lantern, activity-taste, activity-journey, activity-fine,
    #          [JumpBack]activity-quit, [JumpBack]activity-home]
    # 「activity-fine」那一项（自己）由外层 scan 再扫一轮表达，避免递归。
    # 注意 ``退出活动`` / ``回主页`` 是旧图里的逃生口（[JumpBack]），命中即算这一轮结束。
    return bool(
        ctx.scan(
            进关卡片,
            进赏味,
            进短途游历,
            退出活动,
            回主页,
            handle_exceptions,
            timeout=60_000,
            desc="进入玩法",
        )
    )


def 从子界面回主页(ctx: TaskContext) -> bool:
    """旧节点 ``activity-hundred-home``：从活动子界面退回主页。"""
    if not ctx.tap(回主页按钮):
        return False
    return 进佳期(ctx)  # 旧 next：[activity-fine]


def 关掉领奖弹窗(ctx: TaskContext) -> bool:
    """旧节点 ``activity-hundred-quit``：关掉挡路的领奖界面，再继续进活动。"""
    if not ctx.tap(关掉领奖界面):
        return False
    # 旧 next：[activity-fine, activity-hundred-home]
    return 进佳期(ctx) or 从子界面回主页(ctx)


# --------------------------------------------------------------------- 玩法分派


def 进关卡片(ctx: TaskContext) -> bool:
    """旧节点 ``activity-lantern``：点「展会」，然后走它被 option 覆盖后的 next。"""
    if not ctx.tap(OCR("展会", delay=2000, desc="打开展会")):
        return False
    return 展会之后(ctx)


def 展会之后(ctx: TaskContext) -> bool:
    """旧节点 ``activity-lantern`` 的 next —— 两个 option 覆盖后的最终去向。

    旧 ``next`` 是 ``[activity-exhibition-one, activity-Bright-night, activity-lantern]``，
    被两个 option 覆盖：

    * 「选择进程」：``璀璨`` → ``[activity-resplendent]``；``华灯夜`` → ``[activity-Bright-night]``；
      「短途旅游」「赏味」覆盖的是 ``activity-hundred`` —— 本文件里**没有**这个节点
      （整个 pipeline 目录都没有，属于悬空覆盖），所以这两个取值不改变这里。
    * 「选择关卡-活动」：``第一关``..``第六关`` → ``[activity-fire-N]``；
      「非战斗选项选择这个」「华灯夜选这个」只覆盖 ``activity-fail``，不碰这里。

    ``task.option`` 的顺序是「选择进程 → 选择关卡-活动 → 选择战斗次数 → 选择是否放弃」，
    合并时后写的整体替换先写的（``MWATools/MWATaskPipeline.py:281`` 的 ``build_override``
    产出有序数组）。所以**最终结论是：只要关卡挑了具体某一关，就由「选择关卡-活动」
    说了算；否则才轮到「选择进程」的璀璨 / 华灯夜；两个都不是时退回旧的默认 next。**
    """
    关卡 = ctx.text(选项_关卡, "第一关")
    进程 = ctx.text(选项_进程, "短途旅游")

    if 关卡 in 关卡表:
        return 进取火关(ctx, 关卡)
    if 进程 == "璀璨":
        return 进璀璨(ctx)
    if 进程 == "华灯夜":
        return 进华灯夜(ctx)
    # 默认 next 的第三项是 activity-lantern 自己（再点一次「展会」），由外层 scan 负责。
    return bool(ctx.scan(进展会前期, 进华灯夜, timeout=20_000, desc="展会·前期 / 华灯夜"))


def 进展会前期(ctx: TaskContext) -> bool:
    """旧节点 ``activity-exhibition-one``：点「前期」，直接开打。"""
    if not ctx.tap(OCR("前期", delay=2000, desc="选择「前期」")):
        return False
    return 开战(ctx)  # 旧 next：[activity-fight]


def 进璀璨(ctx: TaskContext) -> bool:
    """旧节点 ``activity-resplendent``：点「璀璨」，再选屏幕上出现的那个关卡。

    旧 next：``[activity-fire-one, activity-fire-two, activity-fire-three,
    activity-fire-four-swipe, activity-fire-five-swipe, activity-fire-six-swipe,
    activity-resplendent]`` —— 六个关卡节点挨个试，谁先认出来点谁（自己那项由外层负责）。
    """
    if not ctx.tap(OCR(["璀璨"], delay=2000, desc="进入「璀璨」")):
        return False
    return bool(ctx.scan(试六个关卡, handle_exceptions, timeout=60_000, desc="选择关卡"))


def 试六个关卡(ctx: TaskContext) -> bool:
    """旧节点 ``activity-fire-one`` .. ``activity-fire-six`` 组成的 next 列表。

    认出哪个关卡就去打哪个；认出来之后**不再**试别的关卡，和旧图一致。
    """
    for 关卡 in 关卡表:
        if 选关(ctx, 关卡):
            return 速通战斗(ctx)
    return False


def 进华灯夜(ctx: TaskContext) -> bool:
    """旧节点 ``activity-Bright-night``：点「华灯夜」，从第一盏灯开始。

    旧 next：``[activity-combustion-one, activity-Bright-night]``（自己那项由外层负责）。
    """
    if not ctx.tap(OCR(["华灯夜"], delay=2000, desc="进入「华灯夜」")):
        return False
    return 进第一盏灯(ctx)


def 进第一盏灯(ctx: TaskContext) -> bool:
    """旧节点 ``activity-combustion-one``：选第一盏灯，然后配策略开打。

    旧 next：``[activity-tactics, activity-start, activity-combustion-one]``。
    旧图里「第二盏灯」以后那一串（``activity-combustion-two`` .. ``nine``）没有任何
    节点或 option 指向它们，是死节点，所以这里只打第一盏。
    """
    if not ctx.tap(OCR("一", delay=2000, desc="选第一盏灯")):
        return False
    return bool(ctx.scan(选策略, 重新开战, handle_exceptions, timeout=60_000, desc="准备战斗"))


# --------------------------------------------------------------------- 关卡与战斗


def 进取火关(ctx: TaskContext, 关卡: str) -> bool:
    """旧节点 ``activity-fire-one`` / ``-two`` / ``-three`` / ``-*-swipe`` + ``activity-fire-four`` / ``-five`` / ``-six``。"""
    if not 选关(ctx, 关卡):
        return False
    return 速通战斗(ctx)  # 旧 next：["fast"]


def 选关(ctx: TaskContext, 关卡: str) -> bool:
    """旧节点 ``activity-fire-N``（第四~第六关还要先走一下 ``activity-fire-N-swipe``）。"""
    数字, 要滑动 = 关卡表[关卡]
    if 要滑动:
        # 旧节点 activity-fire-{four,five,six}-swipe：begin [650,275] → end [315,275]，post_delay 3000
        ctx.screen.swipe((650, 275), (315, 275), duration=300, delay=3000, desc=f"{关卡}：左滑找关")
    return ctx.tap(OCR(数字, delay=2000, desc=f"进{关卡}"))


def 速通战斗(ctx: TaskContext) -> bool:
    """旧节点 ``fast`` —— 跨文件接缝，详见模块说明。

    ``fast`` 定义在 ``7_(03)allin.json``（``training.py`` 的模块，对照表第 28 行）。
    「选择战斗次数」这个 option 正是靠整段替换 ``fast.next`` 生效的，指向 ``Start1`` /
    ``Speedrun1x`` / ``Speedrun2x`` / ``Speedrun4x`` / ``Speedrun10x`` / ``allin`` ——
    这些节点同样都在 ``7_(03)allin.json`` 里，本模块 import 不到（规范禁止任务模块
    互相 import）。

    所以这里只照抄 ``fast`` 自己那一步（等 2 秒 → 点「速通」），然后接回**本文件**的
    战斗观测（``盯战斗``）。「点完速通之后打几场、速通没解锁时怎么点开始」仍在
    ``training.py`` 那边，这是需要跟它对齐的一处接缝。
    """
    次数 = ctx.text(选项_次数, "打一次（速通没解锁专用）")
    ctx.step(f"开打（战斗次数选项：{次数}）")
    ctx.screen.sleep(2000)  # 旧 fast 的 pre_delay: 2000
    if ctx.tap(OCR("速通", point=(1030, 660), delay=3000, desc="点「速通」")):  # post_delay 3000
        return 盯战斗(ctx)
    # 没有速通按钮时（旧配置里「打一次（速通没解锁专用）」对应 Start1）退化成点「开始」。
    # ⚠ 这算本模块的行为补充：旧图里 fast 认不出「速通」时整条链会卡住。
    if ctx.tap(OCR("开始", wait_freezes=5000, desc="开始战斗")):
        return 盯战斗(ctx)
    return False


def 盯战斗(ctx: TaskContext) -> bool:
    """战斗观测循环 —— 把下面这些节点的 next 合并成一个循环，逐条保留识别条件与延时。

    它们的 ``next`` 互相成环，逐节点写成函数调用会无限递归：

    * ``activity-fight``             → ``[fight, substitute-shifts, automatic, end]``
    * ``activity-substitute-shifts`` → ``[end, fail, substitute-shifts]``
    * ``activity-automatic``         → ``[substitute-shifts, end, fail, fight, automatic]``
    * ``activity-end``               → ``[continue, end]``
    * ``activity-continue``          → ``[fight, report, continue, fine-swap]``
    * ``activity-report``            → ``[]``（``Shop/01.png``，看到就算这一轮打完）
    * ``activity-fine-swap``         → ``[fight, continue, fine-swap]``
    * ``activity-fail``              → 由「选择是否放弃」覆盖，见 ``战斗失败``
    """
    deadline = time.monotonic() + 900  # 15 分钟，够打完一轮
    while time.monotonic() < deadline:
        ctx.check_cancel()
        if 战斗失败(ctx):  # 旧 activity-fail
            return True
        if 看到战报(ctx):  # 旧 activity-report：这一轮结束了
            return True
        if 点评价(ctx):  # 旧 activity-continue
            continue
        if 点结算(ctx):  # 旧 activity-end
            continue
        if 点代班提示(ctx):  # 旧 activity-substitute-shifts
            continue
        if 点自动(ctx):  # 旧 activity-automatic
            continue
        if 点开始(ctx):  # 旧 activity-fight
            continue
        if 上滑找下一场(ctx):  # 旧 activity-fine-swap
            continue
        time.sleep(0.4)
    ctx.log.warning("等战斗结束超时（15 分钟）")
    return False


def 开战(ctx: TaskContext) -> bool:
    """旧节点 ``activity-fight``：点「开始」进战斗，然后盯战斗里的提示。

    旧节点：OCR「开始」，roi (722,455,558,265)，``post_delay`` 7000。
    """
    if not ctx.tap(OCR("开始", roi=(722, 455, 558, 265), delay=7000, desc="开始战斗")):
        return False
    return 盯战斗(ctx)


def 点开始(ctx: TaskContext) -> bool:
    """旧节点 ``activity-fight``（``盯战斗`` 里用的那一下）。"""
    return ctx.tap(OCR("开始", roi=(722, 455, 558, 265), delay=7000, desc="再点「开始」"))


def 点代班提示(ctx: TaskContext) -> bool:
    """旧节点 ``activity-substitute-shifts``：战斗里的「代班中/敌方/留意」提示。

    旧节点：OCR 词表，roi (453,0,368,246)，``post_delay`` 2000；
    ``next`` 是 ``[activity-end, activity-fail, activity-substitute-shifts]``（第三项由本循环负责）。
    """
    return ctx.tap(
        OCR(["代班中", "敌方", "留意"], roi=(453, 0, 368, 246), delay=2000, desc="关掉战斗提示")
    )


def 点自动(ctx: TaskContext) -> bool:
    """旧节点 ``activity-automatic``：点「自动」让战斗自己打（``post_delay`` 2000）。"""
    return ctx.tap(OCR("自动", delay=2000, desc="开自动战斗"))


def 点结算(ctx: TaskContext) -> bool:
    """旧节点 ``activity-end``：结算/通关弹窗里的「确定」。

    旧节点：OCR「确定」，roi (564,429,716,291)，``post_delay`` 7000。
    """
    if not ctx.tap(OCR("确定", roi=(564, 429, 716, 291), delay=7000, desc="确定（结算）")):
        return False
    return 点评价(ctx)  # 旧 next：[activity-continue, activity-end]


def 点评价(ctx: TaskContext) -> bool:
    """旧节点 ``activity-continue``：评价界面（优/良/中）点最后一条下面那个按钮。

    旧节点带 ``index: -1``（多命中里取最后一条）和 ``target_offset: [0,130,0,0]``，
    ``Cand`` 表达不了 ``index``，所以直接用 ``screen.text`` + ``screen.click``。
    旧 ``next``：``[activity-fight, activity-report, activity-continue, activity-fine-swap]``。
    """
    match = ctx.screen.text(["优", "良", "中"], roi=(1084, 86, 134, 579), index=-1)
    if not match:
        return False
    ctx.screen.click(match, offset=(0, 130, 0, 0), delay=3000, desc="点评价奖励")
    return True


def 看到战报(ctx: TaskContext) -> bool:
    """旧节点 ``activity-report``：战斗结算页（``Shop/01.png``）。

    旧节点是 ``DoNothing`` + ``post_delay`` 2000 + 空 ``next`` —— 看到它这一轮就结束了。
    """
    if not ctx.look(IMG("Shop/01.png")):
        return False
    ctx.screen.sleep(2000)  # 旧 post_delay: 2000
    return True


def 上滑找下一场(ctx: TaskContext) -> bool:
    """旧节点 ``activity-fine-swap``：评价列表往上滑一段再看。

    旧节点：``begin [885,420]`` → ``end [885,270]``，``post_delay`` 3000。
    """
    return ctx.screen.swipe((885, 420), (885, 270), duration=300, delay=3000, desc="上滑找下一场")


def 战斗失败(ctx: TaskContext) -> bool:
    """旧节点 ``activity-fail``：战斗失败弹窗 → 按「选择是否放弃」决定线路。

    ⚠ 这个节点的 ``next`` 被 **3 个** option 覆盖，是旧配置里最容易看错的地方：

    * 「选择关卡-活动」：``非战斗选项选择这个`` → ``[activity-end, activity-fire, start-convened]``；
      ``华灯夜选这个`` → ``[activity-combustion-one, activity-Bright-night]``；
    * 「选择战斗次数」：``非战斗选项选择这个(…专用！！！）`` → 同上前三个；
      ``华灯夜选择这个(…专用！！！）`` → ``[]``（空）；
    * 「选择是否放弃」：``放弃`` → ``[activity-end-fail, activity-fire, start-convened]``；
      ``继续`` / ``打璀璨选择这个`` / ``非战斗选项选择这个`` → ``[activity-end, activity-fire,
      start-convened]``。

    按 ``task.option`` 的顺序（选择进程 → 选择关卡-活动 → 选择战斗次数 → 选择是否放弃）
    合并，``next`` 是整体替换，而「选择是否放弃」的**四个 case 全都覆盖 activity-fail**，
    所以它排在最后、永远赢。这就是旧 GUI / MaaPiCli 的实际行为，原样保留。

    翻译成直白逻辑就是：**战斗失败后看「选择是否放弃」—— ``放弃`` 走放弃链，
    其余三个取值都走「继续」链。**
    """
    if not ctx.tap(
        OCR(
            ["未能", "达到", "完美", "评价", "结算"],
            roi=(406, 248, 459, 227),
            point=(775, 435),
            delay=2000,
            desc="战斗失败弹窗",
        )
    ):
        return False
    放弃 = ctx.text(选项_放弃, "放弃")
    if 放弃 == "放弃":
        ctx.step("战斗失败：按选项「放弃」")
        # 旧 next：[activity-end-fail, activity-fire, start-convened]
        return bool(
            ctx.scan(放弃确认, 取火兜底, 已在主界面, handle_exceptions, timeout=120_000, desc="放弃这次战斗")
        )
    ctx.step(f"战斗失败：按选项「{放弃}」继续")
    # 旧 next：[activity-end, activity-fire, start-convened]
    return bool(
        ctx.scan(点结算, 取火兜底, 已在主界面, handle_exceptions, timeout=120_000, desc="继续战斗")
    )


def 放弃确认(ctx: TaskContext) -> bool:
    """旧节点 ``activity-end-fail``：放弃流程里的那一次「确定」（``post_delay`` 7000）。

    旧 next：``[activity-abandon, activity-end-fail, activity-start]``（第二项是自己）。
    """
    if not ctx.tap(OCR("确定", roi=(564, 429, 716, 291), delay=7000, desc="确定（放弃）")):
        return False
    return 确认放弃(ctx) or 重新开战(ctx)


def 确认放弃(ctx: TaskContext) -> bool:
    """旧节点 ``activity-abandon``：点「放弃挑战」。

    旧节点：OCR 词表 ``[放弃, 挑战]``，roi (992,542,288,178)，``post_delay`` 5000；
    旧 next：``[activity-end-fail, activity-start]``（由 ``放弃确认`` / ``盯战斗`` 负责）。
    """
    return ctx.tap(OCR(["放弃", "挑战"], roi=(992, 542, 288, 178), delay=5000, desc="确认放弃挑战"))


def 重新开战(ctx: TaskContext) -> bool:
    """旧节点 ``activity-start``：再开一局的「开始 / 继续」。

    旧节点：OCR 词表 ``[开始, 继续]``，roi (963,418,314,221)，``post_delay`` 3000；
    旧 next：``[activity-tactics, activity-start]``（第二项是自己）。
    """
    if not ctx.tap(OCR(["开始", "继续"], roi=(963, 418, 314, 221), delay=3000, desc="开始/继续挑战")):
        return False
    return 选策略(ctx)


def 选策略(ctx: TaskContext) -> bool:
    """旧节点 ``activity-tactics``：选「策略」。

    旧节点：OCR「策略」，roi (21,0,266,153)，``target`` 写死 ``[360,315,0,0]``（点这个绝对坐标），
    ``post_delay`` 2000；旧 next：``[activity-fight, activity-tactics]``（第二项是自己）。
    """
    if not ctx.tap(OCR("策略", roi=(21, 0, 266, 153), point=(360, 315), delay=2000, desc="选策略")):
        return False
    return 开战(ctx)


def 取火兜底(ctx: TaskContext) -> bool:
    """旧节点 ``activity-fire``：战斗失败链里的「取火」兜底（战斗结束时可能停在这一屏）。

    旧节点：OCR「取火」，``post_delay`` 3000（**没有写 ``action``，默认是 DoNothing，
    所以只看不点** —— 这一点极易误读）；
    旧 next：``[activity-quit, activity-home, start-convened]``。
    """
    if not ctx.look(OCR("取火", desc="确认停在「取火」这一屏")):
        return False
    ctx.screen.sleep(3000)  # 旧 post_delay: 3000
    return 退出活动(ctx)


def 已在主界面(ctx: TaskContext) -> bool:
    """旧节点 ``start-convened``（= ``Exception-handling-convened``）：主界面标记。

    旧节点是 ``DoNothing`` + ``post_delay`` 2000，所以这里只看不点，
    用的是 ``MWATools`` 的共用件 ``MAIN_PAGE``（``Startup/11.png``，roi 906,340,170,205）。
    """
    if not ctx.look(MAIN_PAGE):
        return False
    ctx.screen.sleep(2000)  # 旧 post_delay: 2000
    return True


# --------------------------------------------------------------------- 退出


def 退出活动(ctx: TaskContext) -> bool:
    """旧节点 ``activity-quit``：反复点「关掉活动界面」，直到回主页 / 主界面。

    旧 ``next``：``[activity-home, activity-quit, start-convened]`` —— 第一项是回主页，
    第二项是自己（再点一次），第三项是已经站在主界面。这里写成一个循环，不递归。
    """
    for _ in range(6):
        ctx.check_cancel()
        if ctx.tap(回主页按钮):  # 旧 next 第一项 activity-home
            return True
        if ctx.look(MAIN_PAGE):  # 旧 next 第三项 start-convened（只看不点）
            return True
        if not ctx.tap(关掉领奖界面):  # 旧 next 第二项 activity-quit（再点一次）
            return False
    return False


# --------------------------------------------------------------------- 赏味（筹备）


def 进赏味(ctx: TaskContext) -> bool:
    """旧节点 ``activity-taste``：点「筹备」，然后把七道菜按顺序领一遍。

    旧 next：``[activity-taste-one, .., activity-taste-seven]`` —— 七个节点挨个探，
    某一道不在就试下一道（旧图也是这样，谁先认出来走谁）。
    """
    if not ctx.tap(OCR("筹备", delay=2000, desc="进「赏味」筹备页")):
        return False
    领到 = 0
    for index in range(len(赏味七味)):
        ctx.check_cancel()
        if 领一道赏味(ctx, index):
            领到 += 1
    if not 领到:
        ctx.log.warning("七道赏味一个都没认出来，可能没进「筹备」页")
        return False
    return 退出活动(ctx)  # 旧图最后一站的 next 是 activity-quit


def 领一道赏味(ctx: TaskContext, index: int) -> bool:
    """旧节点 ``activity-taste-N`` → ``activity-skip-N`` → ``activity-taste-give-N``。

    * ``activity-taste-N``：OCR 菜名（各自 roi），``post_delay`` 3000；
    * ``activity-skip-N``：点 ``activity/04.png`` 跳过动画，roi (1103,0,177,165)，``post_delay`` 3000；
    * ``activity-taste-give-N``：点「获得物资」，roi (964,115,245,487)，``post_delay`` 2000
      （``next`` 里含自己 → 收完为止）。

    旧 ``next`` 的兜底（``taste-N`` / ``skip-N`` 里的自己、以及 ``skip-N`` → ``taste-(N+1)``）
    由 ``进赏味`` 的循环负责。
    """
    词, roi = 赏味七味[index]
    if not ctx.tap(OCR(词, roi=roi, delay=3000, desc=f"赏味：{词}")):
        return False
    # 旧 next：[activity-skip-N, activity-taste-N] —— 跳过动画的按钮可能要等一下才出来
    if not ctx.retry(
        lambda: ctx.tap(IMG("activity/04.png", roi=(1103, 0, 177, 165), delay=3000, desc="跳过赏味动画")),
        timeout=10_000,
        interval=500,
        desc=f"{词}：等跳过按钮",
    ):
        return False
    for _ in range(30):
        ctx.check_cancel()
        if ctx.tap(OCR(["获", "得", "物", "资"], roi=(964, 115, 245, 487), delay=2000, desc="收取物资")):
            continue
        break
    return True


# --------------------------------------------------------------------- 短途游历


def 进短途游历(ctx: TaskContext) -> bool:
    """旧节点 ``activity-journey`` → ``activity-task`` → ``activity-weekly``。"""
    if not ctx.tap(OCR("短途游历", roi=(0, 244, 219, 163), delay=2000, desc="进「短途游历」")):
        return False
    # 旧 next：[activity-task]
    if not ctx.tap(OCR("任务", delay=2000, desc="打开任务页")):
        return False
    # 旧 activity-task 的 next：[activity-weekly]
    if not ctx.tap(OCR("周常", delay=2000, desc="切到「周常」")):
        return False
    # 旧 activity-weekly 的 next：[activity-receive, activity-accomplishment, activity-journey-quit]
    if not ctx.scan(领周常, 看成就, 关掉领奖界面, handle_exceptions, timeout=120_000, desc="领周常奖励"):
        return False
    return 退出活动(ctx)


def 领周常(ctx: TaskContext) -> bool:
    """旧节点 ``activity-receive`` / ``activity-give`` / ``activity-accomplishment`` /
    ``activity-journey-quit``（四个节点的 next 互相指来指去 → 写成一个循环）。

    * ``activity-receive``：点「一键领取」，roi (345,496,935,224)，``post_delay`` 2000；
    * ``activity-give``：点「获得物资」，roi (964,115,245,487)，``post_delay`` 2000；
    * ``activity-accomplishment``：切「成就」页（``post_delay`` 2000）；
    * ``activity-journey-quit``：领完了点「关掉领奖界面」（``receive_reward/01.png``，
      ``post_delay`` 2000）。
    """
    for _ in range(40):
        ctx.check_cancel()
        if ctx.tap(OCR(["一键", "领取"], roi=(345, 496, 935, 224), delay=2000, desc="一键领取")):
            continue
        if ctx.tap(OCR(["获", "得", "物", "资"], roi=(964, 115, 245, 487), delay=2000, desc="收下奖励")):
            continue
        if ctx.tap(OCR("成就", delay=2000, desc="切到「成就」页")):
            continue
        if ctx.tap(关掉领奖界面):  # 旧 activity-journey-quit
            return True
        return False
    return False


def 看成就(ctx: TaskContext) -> bool:
    """旧节点 ``activity-accomplishment``（``进短途游历`` 的兜底入口之一）。

    旧节点：OCR「成就」，``post_delay`` 2000；旧 next：``[activity-receive, activity-journey-quit]``。
    """
    if not ctx.tap(OCR("成就", delay=2000, desc="切到「成就」页")):
        return False
    return 领周常(ctx)


def 回主页(ctx: TaskContext) -> bool:
    """旧节点 ``activity-home``：点左上角回主页（旧节点没有 ``next``，到这儿算走完）。"""
    return ctx.tap(IMG("Startup/10.png", delay=2000, desc="回主页"))
