"""派遣公司：一条龙把派遣公司里能领的都领掉。

移植自旧流水线入口 ``3_dispath_company.json``（节点 ``dispatch_company_all`` /
``dc_back``）和它拉起来的六个支线文件：

* ``3_(1)resources_induction.json`` —— 资源 / 感应 / 好感 / 武库
* ``3-(2)_vending_machine.json``     —— 售卖机（办公区）领奖
* ``3_(3)_dispatch_social.json``     —— 社教模拟仪 + 社会指南制造
* ``3_(4)_fabricate.json``           —— 制造台十种配方
* ``3_(5)_tea.json``                 —— 茶室喝茶
* ``3_(6)_vitality.json``            —— 宿舍领活力值

旧写法里「用选项选分支」是把 ``pipeline_override`` 打在某个中间节点的 ``next``
上：「领取资源、好感、售卖机」改 ``entry_one.next``、「社教模拟仪」改
``entry_dispath_three.next``、「制造物品」改 ``entry_dispath_four.next``、
「是否喝茶」改 ``tea.next``、「是否领取活力值」改 ``vitality.next``。Python 里
不再需要这种绕圈：每个阶段读自己的选项值，用 ``if`` / 字典查表决定走哪条链。

旧写法里还有第二种绕圈：阶段之间不靠调用，而靠链尾 ``next`` 硬连（例如
``dispath_home.next`` 就是 ``entry_dispath_four``、``fabricate_home.next`` 就是
``tea``）。这里改成主流程顺序往下走，每个阶段走完自然返回给 ``派遣公司``。

每个函数上面的注释标出它对应旧 JSON 的哪个节点名，方便回退核对。
"""

from __future__ import annotations

from typing import Callable, Optional

from MWATools.MWATask import (
    Cand,
    Choice,
    IMG,
    OCR,
    Option,
    TaskContext,
    handle_exceptions,
    task,
)

# --------------------------------------------------------------------- 小常量

#: 旧 JSON 里反复出现的模板，各支线的点击参数完全一样，只是 ``post_delay`` 不同，
#: 所以带延时的那些在调用处就地写 ``IMG(...)``。
派遣公司图标 = IMG("Company/d_company.png", delay=7000, desc="进出派遣公司")
点空白 = IMG("Company/click_space.png", roi=(988, 107, 240, 480), desc="点击空白")

#: 旧 ``Collect/06.png``：关掉当前面板。旧 JSON 里它被 ``entry_back`` /
#: ``dc_back`` / ``donshe_back`` / ``dispath_back`` / ``fabricate_back`` /
#: ``tea_back`` / ``vitality_back`` 共用，各自的 ``post_delay`` 是 0 / 3000 / 7000。


# --------------------------------------------------------------------- 选项
#
# key / case 名 / 默认值全部对齐 assets/interface.json 的任务「派遣公司」：
# 没写 default_case，所以默认值就是第一个 case。


选项_资源 = Option(
    "领取资源、好感、售卖机",
    label="领取资源、好感、售卖机",
    kind="select",
    default="领取奖励",
    choices=(Choice("领取奖励"), Choice("不领取")),
    description="进派遣公司把资源、感性、好感、售卖机的奖励一次领掉；不领取就只退出建筑",
)

选项_社教 = Option(
    "社教模拟仪",
    label="社教模拟仪",
    kind="select",
    default="初级社会指南",
    choices=(
        Choice("初级社会指南"),
        Choice("中级社会指南"),
        Choice("高级社会指南"),
        Choice("进阶社会指南"),
        Choice("不领取"),
    ),
    description="用社教模拟仪制造哪一档社会指南",
)

选项_制造 = Option(
    "制造物品",
    label="制造物品",
    kind="select",
    default="蓝色装备",
    choices=(
        Choice("蓝色装备"),
        Choice("铜石墨条（蓝装升级）"),
        Choice("银石墨条（黄装升级）"),
        Choice("100装备经验"),
        Choice("1型钢材"),
        Choice("资质证明1"),
        Choice("资质证明2"),
        Choice("高级制造申请"),
        Choice("2型钢材"),
        Choice("资质证明3"),
        Choice("不制造"),
    ),
    description="在制造台制造哪一件物品",
)

选项_喝茶 = Option(
    "是否喝茶",
    label="是否喝茶",
    kind="select",
    default="喝茶",
    choices=(Choice("喝茶"), Choice("不喝茶")),
    description="要不要去茶室喝茶（倒茶 → 两次确认 → 摆茶具 → 邀请 → 品茗）",
)

选项_活力 = Option(
    "是否领取活力值",
    label="是否领取活力值",
    kind="select",
    default="领取",
    choices=(Choice("领取"), Choice("不领取")),
    description="要不要进宿舍领活力值",
)


# --------------------------------------------------------------------- 任务


@task(
    "派遣公司",
    group="派遣",
    order=100,
    options=(选项_资源, 选项_社教, 选项_制造, 选项_喝茶, 选项_活力),
    description="派遣公司一条龙：资源/好感/售卖机 → 社教模拟仪 → 制造物品 → 喝茶 → 活力值",
)
def 派遣公司(ctx: TaskContext) -> bool:
    """旧节点 ``dispatch_company_all``。

    旧 ``next`` 是 ``[entry_one, dispath_company_collect, fabricate, tea, vitality]``，
    五个阶段串成一条线（而 ``entry_two`` 售卖机是挂在 ``entry_one`` 链尾的）。
    这里直接顺序执行；任何一段没走通就返回 False，交给上层决定要不要继续。
    """
    if not 领取资源好感售卖机(ctx):
        return False
    if not 社教模拟仪(ctx):
        return False
    if not 制造物品(ctx):
        return False
    if not 喝茶(ctx):
        return False
    if not 领取活力值(ctx):
        return False
    return True


# ----------------------------------------------------------- 第一段：进公司领奖
# 旧 ``3_(1)resources_induction.json`` ——「资源 → 感应 → 好感 → 武库」。


def 领取资源好感售卖机(ctx: TaskContext) -> bool:
    """旧节点 ``entry_one``（+ 链尾的 ``entry_two``）。

    旧 ``entry_one.next`` 默认是 ``[entry_dispath_one, dispath_resources, entry_back,
    entry_convened, [JumpBack]Exception-handling-*]``，选项把它整条换成
    ``"entry_dispath_one"``（领取奖励）或 ``["entry_back", "entry_convened"]``
    （不领取）。不领取时旧写法经 ``entry_back`` / ``entry_convened`` 直接跳到
    ``dispath_company_collect``，连售卖机一起跳过，这里保持一致。
    """
    ctx.step("派遣公司：领取资源、好感、售卖机")
    if ctx.text("领取资源、好感、售卖机", "领取奖励") != "领取奖励":
        return bool(
            ctx.scan(
                关掉公司面板,
                确认已在主界面,
                handle_exceptions,
                timeout=20_000,
                desc="跳过派遣公司",
            )
        )
    if not 进派遣公司(ctx):
        return False
    return 售卖机领奖(ctx)


def 进派遣公司(ctx: TaskContext) -> bool:
    """旧节点 ``entry_dispath_one``：点进派遣公司建筑，把能领的都领一遍。

    旧 next：``[dispath_resources, click_space, donshe, weapons, entry_two,
    [JumpBack]Exception-handling-*]``。其中 ``entry_two``（售卖机）已经拎成
    ``领取资源好感售卖机`` 里的后一段。
    """
    if not ctx.tap(派遣公司图标):
        return False
    return bool(
        ctx.scan(
            领派遣资源,
            点空白继续,
            领好感,
            进武器店,
            handle_exceptions,
            timeout=90_000,
            desc="在派遣公司里领取",
        )
    )


def 领派遣资源(ctx: TaskContext) -> bool:
    """旧节点 ``dispath_resources``：点右下角的资源图标。

    旧 next：``[no_collect_induction, click_space, dispath_resources]`` —— 自己在
    列表里（领不到就再点一次），这里交给外层 ``scan`` 重试。
    """
    if not ctx.tap(
        IMG("Company/c_resources.png", roi=(1009, 533, 271, 187), delay=2500, desc="派遣资源图标")
    ):
        return False
    return bool(ctx.scan(资源暂时没有, 点空白继续, timeout=20_000, desc="领派遣资源"))


def 资源暂时没有(ctx: TaskContext) -> bool:
    """旧节点 ``no_collect_induction``：只识别「暂时没有」，什么都不点。

    旧 ``action`` 是 ``DoNothing``；旧 next 是 ``[donshe, weapons,
    no_collect_induction]``，也就是资源这边领完了，转去领好感和武库。
    """
    if not ctx.look(OCR("暂时没有", desc="暂时没有可领的资源")):
        return False
    return bool(ctx.scan(领好感, 进武器店, timeout=30_000, desc="资源已领完，转去好感/武库"))


def 点空白继续(ctx: TaskContext) -> bool:
    """旧节点 ``click_space``：点一下空白处，把刚弹出来的奖励动画按掉。

    旧 next：``[click_space, collect_induction]``。
    """
    if not ctx.tap(点空白):
        return False
    return bool(ctx.scan(领取感应奖励, timeout=20_000, desc="点空白继续"))


def 领取感应奖励(ctx: TaskContext) -> bool:
    """旧节点 ``collect_induction``：点右下角的感应图标。

    旧 next：``[no_collect_induction, collect_induction_click, collect_induction]``。
    """
    if not ctx.tap(
        IMG("Company/c_induction.png", roi=(913, 548, 184, 172), delay=2500, desc="派遣感应图标")
    ):
        return False
    return bool(ctx.scan(资源暂时没有, 感应领取确认, timeout=20_000, desc="领感应奖励"))


def 感应领取确认(ctx: TaskContext) -> bool:
    """旧节点 ``collect_induction_click``：感应弹窗里的领取按钮。

    旧 next：``[collect_induction_click, donshe, weapons]``。
    """
    if not ctx.tap(
        IMG("Company/c_induction_click.png", roi=(408, 47, 566, 168), delay=3000, desc="确认领取感应")
    ):
        return False
    return bool(ctx.scan(领好感, 进武器店, timeout=30_000, desc="感应领完，转去好感/武库"))


def 领好感(ctx: TaskContext) -> bool:
    """旧节点 ``donshe``：点建筑里的好感图标。

    旧 next：``[donshe_click_space, weapons, donshe]``。
    """
    if not ctx.tap(
        IMG("Company/donshe.png", roi=(451, 477, 227, 211), delay=3000, desc="领取好感")
    ):
        return False
    return bool(ctx.scan(好感点空白, 进武器店, timeout=30_000, desc="领好感"))


def 好感点空白(ctx: TaskContext) -> bool:
    """旧节点 ``donshe_click_space``：好感领完点空白收尾。

    旧 next：``[weapons, entry_two, donshe_back]``（``entry_two`` 已挪到主流程）。
    """
    if not ctx.tap(点空白):
        return False
    return bool(ctx.scan(进武器店, 好感返回, timeout=30_000, desc="好感收尾"))


def 进武器店(ctx: TaskContext) -> bool:
    """旧节点 ``weapons``：点左下角那个「间」，进武库/订购界面。

    旧识别是 OCR「间」，roi (275,280,175,200) 再加 ``target_offset`` (75,15)；
    旧 next：``[weapons_click, weapons_two, donshe_back, weapons_home]``。
    """
    if not ctx.tap(
        OCR("间", roi=(275, 280, 175, 200), offset=(75, 15, 0, 0), delay=3000, desc="进武库")
    ):
        return False
    return bool(
        ctx.scan(武器领取, 武器订购提示, 好感返回, 武器回主页, timeout=30_000, desc="武库")
    )


def 武器领取(ctx: TaskContext) -> bool:
    """旧节点 ``weapons_click``：点「得」领取。

    旧 next：``[donshe_back, entry_two]``。
    """
    if not ctx.tap(OCR("得", delay=2000, desc="领取武库奖励")):
        return False
    return bool(ctx.scan(好感返回, timeout=15_000, desc="武库领取收尾"))


def 武器订购提示(ctx: TaskContext) -> bool:
    """旧节点 ``weapons_two``：识别底部的「订购」栏 —— 只判断，不点。

    旧 ``action`` 是 ``DoNothing``；旧 next：``[weapons_home]``。
    """
    if not ctx.look(OCR("订购", roi=(0, 610, 1280, 110), desc="底部订购栏")):
        return False
    return 武器回主页(ctx)


def 武器回主页(ctx: TaskContext) -> bool:
    """旧节点 ``weapons_home``：点 ``Startup/10.png`` 回主页（旧 next：``[entry_two]``）。"""
    return ctx.tap(IMG("Startup/10.png", desc="回主页"))


def 好感返回(ctx: TaskContext) -> bool:
    """旧节点 ``donshe_back``：关掉当前面板（旧 next：``[entry_two]``）。

    旧 ``post_delay`` 是 3000。
    """
    return ctx.tap(IMG("Collect/06.png", delay=3000, desc="关掉当前面板"))


# ------------------------------------------------------- 第二段：售卖机（办公区）
# 旧 ``3-(2)_vending_machine.json``。


def 售卖机领奖(ctx: TaskContext) -> bool:
    """旧节点 ``entry_two``：售卖机（办公区）领奖。

    旧 next：``[vending_machine, vending_machine_reward, entry_dispath_two,
    vending_home, entry_back, [JumpBack]Exception-handling-*]``。
    """
    ctx.step("派遣公司：售卖机领奖")
    return bool(
        ctx.scan(
            点办公区,
            领售卖机奖励,
            再进派遣公司,
            售卖机回主页,
            关掉公司面板,
            handle_exceptions,
            timeout=90_000,
            desc="售卖机领奖",
        )
    )


def 点办公区(ctx: TaskContext) -> bool:
    """旧节点 ``vending_machine``：OCR「办公」，点售卖机所在的办公区。

    旧 next：``[vending_machine_reward, vending_home, entry_back]``。
    """
    if not ctx.tap(OCR("办公", roi=(345, 51, 345, 266), delay=3000, desc="点办公区")):
        return False
    return bool(ctx.scan(领售卖机奖励, 售卖机回主页, 关掉公司面板, timeout=30_000, desc="售卖机"))


def 领售卖机奖励(ctx: TaskContext) -> bool:
    """旧节点 ``vending_machine_reward``：点售卖机上的奖励。

    旧 ``target`` 是绝对矩形 ``[203, 69, 41, 34]``（点它的中心，所以在识别框之外），
    也就是绝对点 (223, 86)。旧 next：``[coin_flip, vending_machine_reward]``。
    """
    if not ctx.tap(
        IMG(
            "Company/vending_machine_reward.png",
            roi=(123, 11, 231, 201),
            point=(223, 86),
            delay=3000,
            desc="领取售卖机奖励",
        )
    ):
        return False
    return bool(ctx.scan(投币, timeout=30_000, desc="售卖机发奖"))


def 投币(ctx: TaskContext) -> bool:
    """旧节点 ``coin_flip``：投币动画（点一下，再等画面静止 5 秒）。

    旧 ``post_wait_freezes`` 是 5000；旧 next：``[coin_flip_click_space, coin_flip]``。
    """
    if not ctx.tap(
        IMG("Company/coin_flip.png", roi=(771, 293, 340, 232), wait_freezes=5000, desc="投币")
    ):
        return False
    return bool(ctx.scan(投币点空白, timeout=30_000, desc="投币动画"))


def 投币点空白(ctx: TaskContext) -> bool:
    """旧节点 ``coin_flip_click_space``：投币完点空白收尾。

    旧 next：``[coin_flip_click_space, vending_home]``。
    """
    if not ctx.tap(OCR("点击空白", roi=(988, 107, 240, 480), delay=3000, desc="点击空白")):
        return False
    return bool(ctx.scan(售卖机回主页, timeout=30_000, desc="投币收尾"))


def 再进派遣公司(ctx: TaskContext) -> bool:
    """旧节点 ``entry_dispath_two``：又看到派遣公司图标，再点一次。

    旧 next：``[entry_dispath_two, vending_machine, vending_machine_reward]``。
    """
    if not ctx.tap(IMG("Company/d_company.png", delay=7000, desc="再次进入派遣公司")):
        return False
    return bool(ctx.scan(点办公区, 领售卖机奖励, timeout=60_000, desc="再进派遣公司"))


def 售卖机回主页(ctx: TaskContext) -> bool:
    """旧节点 ``vending_home``：点 ``Startup/10.png`` 回主页。

    旧 next：``[dispath_company_collect]``，也就是接去社教那一段。
    """
    return ctx.tap(IMG("Startup/10.png", delay=5000, desc="回主页"))


def 关掉公司面板(ctx: TaskContext) -> bool:
    """旧节点 ``entry_back``，也是 ``3_dispath_company.json`` 里的 ``dc_back``。

    两个节点在旧 JSON 里完全一样（``Collect/06.png``，无延时，next 都是
    ``[dispath_company_collect]``），所以合成一个。
    """
    return ctx.tap(IMG("Collect/06.png", desc="关掉当前面板"))


def 确认已在主界面(ctx: TaskContext) -> bool:
    """旧节点 ``entry_convened``：认出 ``Startup/11.png``（已经在主界面）。

    旧 next：``[dispath_company_collect]``。
    """
    if not ctx.look(IMG("Startup/11.png", roi=(906, 340, 170, 205))):
        return False
    ctx.screen.sleep(3000)  # 旧 post_delay: 3000
    return True


# -------------------------------------------------------------- 第三段：社教模拟仪
# 旧 ``3_(3)_dispatch_social.json``。


def 社教模拟仪(ctx: TaskContext) -> bool:
    """旧节点 ``dispath_company_collect``（+ ``entry_dispath_three``）。

    旧 next：``[entry_dispath_three, dispath_back, dispath_convened, 异常处理]``；
    选项「社教模拟仪」覆盖的是 ``entry_dispath_three.next``。
    """
    ctx.step("派遣公司：社教模拟仪")
    return bool(
        ctx.scan(
            进社教模拟仪,
            退出社教,
            社教已在主界面,
            handle_exceptions,
            timeout=90_000,
            desc="社教模拟仪",
        )
    )


def 进社教模拟仪(ctx: TaskContext) -> bool:
    """旧节点 ``entry_dispath_three``：点进派遣公司，再按选项选一档指南。

    旧 next 是十项长表 ``[dispatch_social_one ... _four, dispath_back, 异常处理]``；
    选项把它换成对应的 ``dispatch_social_*``，或者 ``["dispath_back",
    "dispath_convened"]``（不领取 —— 旧写法仍然会先点进建筑再退出来，照做）。
    """
    if not ctx.tap(派遣公司图标):
        return False
    档位 = ctx.text("社教模拟仪", "初级社会指南")
    if 档位 == "不领取":
        return bool(ctx.scan(退出社教, 社教已在主界面, timeout=20_000, desc="跳过社教模拟仪"))
    return bool(
        ctx.scan(
            社教档位.get(档位, 选初级社会指南),
            timeout=60_000,
            desc=f"社教模拟仪：{档位}",
        )
    )


def 选初级社会指南(ctx: TaskContext) -> bool:
    """旧节点 ``dispatch_social_one`` → ``Beginner_Social_Guide``。"""
    return _选社会指南(ctx, "Company/beginner_social_guide.png", (7, 146, 420, 134), "初级社会指南")


def 选中级社会指南(ctx: TaskContext) -> bool:
    """旧节点 ``dispatch_social_two`` → ``Intermediate_Social_Guide``。"""
    return _选社会指南(
        ctx, "Company/Intermediate_Social_Guide.png", (6, 277, 419, 124), "中级社会指南"
    )


def 选高级社会指南(ctx: TaskContext) -> bool:
    """旧节点 ``dispatch_social_three`` → ``Advanced_Social_Guide``。"""
    return _选社会指南(ctx, "Company/Advanced_Social_Guide.png", (4, 393, 428, 132), "高级社会指南")


def 选进阶社会指南(ctx: TaskContext) -> bool:
    """旧节点 ``dispatch_social_four`` → ``Advanced_Sociology``。"""
    return _选社会指南(ctx, "Company/Advanced_Sociology.png", (8, 524, 422, 131), "进阶社会指南")


def _选社会指南(
    ctx: TaskContext,
    指南图: str,
    指南roi: tuple[int, int, int, int],
    说明: str,
) -> bool:
    """旧节点 ``dispatch_social_one`` / ``_two`` / ``_three`` / ``_four`` 的公共部分。

    这四个节点本身就是一模一样的（都点 ``Company/social_guidence.png``，
    连 roi 都相同），差别只在后面点哪一档指南；旧 next 都是
    ``[<对应的指南节点>, <自己>]``，点不到指南就把社教图标再点一次 —— 这里靠外层
    ``scan`` 重试。
    """
    if not ctx.tap(
        IMG("Company/social_guidence.png", roi=(9, 366, 249, 196), delay=2000, desc="社教模拟仪")
    ):
        return False
    if not ctx.tap(IMG(指南图, roi=指南roi, delay=2000, desc=说明)):
        return False
    return 社教制造(ctx)


def 社教制造(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_max``：把制造数量拉满。

    旧 next：``[fabricate_social_book, fabricate_max]``。
    """
    if not ctx.tap(
        IMG("Company/fabricate_max.png", roi=(1040, 512, 80, 71), delay=2000, desc="制造数量拉满")
    ):
        return False
    return bool(ctx.scan(制造社会指南, timeout=30_000, desc="制造社会指南"))


def 制造社会指南(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_social_book``：点「制造」。

    旧 next：``[verify_fabricate, fabricate_social_book]``。
    """
    if not ctx.tap(
        IMG("Company/fabricate_social_book.png", roi=(870, 618, 301, 73), delay=2000, desc="点制造")
    ):
        return False
    return bool(ctx.scan(确认社会指南, timeout=30_000, desc="确认制造"))


def 确认社会指南(ctx: TaskContext) -> bool:
    """旧节点 ``verify_fabricate``：确认制造。

    旧 next：``[dispath_home, verify_fabricate]``。
    """
    if not ctx.tap(
        IMG("Company/verify_fabricate.png", roi=(678, 387, 188, 76), delay=2000, desc="确认制造")
    ):
        return False
    return 社教回主页(ctx)


def 社教回主页(ctx: TaskContext) -> bool:
    """旧节点 ``dispath_home``（旧 next：``[entry_dispath_four]``，现在由主流程接制造）。"""
    return ctx.tap(IMG("Startup/10.png", delay=5000, desc="回主页"))


def 退出社教(ctx: TaskContext) -> bool:
    """旧节点 ``dispath_back``（旧 next：``[entry_dispath_four]``）。

    旧 ``post_delay`` 是 7000。
    """
    return ctx.tap(IMG("Collect/06.png", delay=7000, desc="退出派遣公司"))


def 社教已在主界面(ctx: TaskContext) -> bool:
    """旧节点 ``dispath_convened``（旧 next：``[entry_dispath_four]``）。"""
    if not ctx.look(IMG("Startup/11.png", roi=(906, 340, 170, 205))):
        return False
    ctx.screen.sleep(3000)  # 旧 post_delay: 3000
    return True


# ---------------------------------------------------------------- 第四段：制造物品
# 旧 ``3_(4)_fabricate.json``。


def 制造物品(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate``（+ ``entry_dispath_four``）。

    旧 ``fabricate.next`` 是 ``[entry_dispath_four, dc_back, 异常处理]``；选项
    「制造物品」覆盖的是 ``entry_dispath_four.next``：把「十种配方都试一遍」换成
    某一个 ``fabricate_all_*``，或者 ``["fabricate_back", "fabricate_convened"]``。
    """
    ctx.step("派遣公司：制造物品")
    return bool(
        ctx.scan(进制造台, 关掉公司面板, handle_exceptions, timeout=150_000, desc="制造物品")
    )


def 进制造台(ctx: TaskContext) -> bool:
    """旧节点 ``entry_dispath_four``：点进派遣公司，再按选项造一件东西。"""
    if not ctx.tap(派遣公司图标):
        return False
    配方 = ctx.text("制造物品", "蓝色装备")
    if 配方 == "不制造":
        return bool(ctx.scan(退出制造, 制造已在主界面, timeout=20_000, desc="跳过制造"))
    return bool(
        ctx.scan(制造清单.get(配方, 制造蓝色装备), timeout=120_000, desc=f"制造：{配方}")
    )


def _制造一件(ctx: TaskContext, 目标: Cand, *, 滑动: int = 0) -> bool:
    """旧节点 ``fabricate_all_one`` 到 ``fabricate_all_ten`` 的公共部分。

    每一条都是「点左边的配方分类（``Company/10.png``）→ 可能往下滑几次
    （``fabricate_*_Swipe`` / ``*_Swipe_2``）→ 点具体物件（``fabricate_*``）」，
    然后统一接 ``fabricate_max_2`` 那一段（见 ``_制造收尾``）。
    """
    if not ctx.tap(IMG("Company/10.png", roi=(17, 272, 151, 137), delay=3000, desc="配方分类")):
        return False
    for index in range(滑动):
        # 旧 Swipe 节点：把配方列表往上拨 (265,305) → (265,160)。
        # 第一次 ``fabricate_*_Swipe`` 的 post_delay 是 3000，第二次
        # ``*_Swipe_2`` 是 5000。
        ctx.screen.swipe(
            (265, 305),
            (265, 160),
            duration=300,
            delay=3000 if index == 0 else 5000,
            desc="翻配方列表",
        )
    if not ctx.tap(目标):
        return False
    return _制造收尾(ctx)


def _制造收尾(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_max_2`` → ``fabricate_social_book_2`` →
    ``verify_fabricate_2`` → ``fabricate_home``（拉满 → 制造 → 确认 → 回主页）。"""
    if not ctx.tap(
        IMG("Company/fabricate_max.png", roi=(1040, 512, 80, 71), delay=3000, desc="制造数量拉满")
    ):
        return False
    if not ctx.tap(
        IMG("Company/fabricate_social_book.png", roi=(870, 618, 301, 73), delay=3000, desc="点制造")
    ):
        return False
    if not ctx.tap(
        IMG("Company/verify_fabricate.png", roi=(678, 387, 188, 76), delay=3000, desc="确认制造")
    ):
        return False
    return ctx.tap(IMG("Startup/10.png", delay=5000, desc="回主页"))


def 制造蓝色装备(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_all_one`` → ``fabricate_one``。"""
    return _制造一件(ctx, IMG("Company/11.png", delay=2000, desc="蓝色装备"))


def 制造铜石墨条(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_all_two`` → ``fabricate_two``（OCR「饰铜」）。"""
    return _制造一件(ctx, OCR("饰铜", delay=2000, desc="铜石墨条"))


def 制造银石墨条(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_all_three`` → ``fabricate_three``（OCR「银」）。"""
    return _制造一件(ctx, OCR("银", delay=2000, desc="银石墨条"))


def 制造装备经验(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_all_four`` → ``fabricate_four``。"""
    return _制造一件(ctx, IMG("Company/14.png", delay=2000, desc="100装备经验"))


def 制造1型钢材(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_all_five`` → ``fabricate_five_Swipe`` → ``fabricate_five``。"""
    return _制造一件(
        ctx, IMG("Company/15.png", offset=(200, 0, 0, 0), delay=2000, desc="1型钢材"), 滑动=1
    )


def 制造资质证明1(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_all_six`` → ``fabricate_six_Swipe`` → ``fabricate_six``。"""
    return _制造一件(
        ctx, IMG("Company/16.png", offset=(200, 0, 0, 0), delay=2000, desc="资质证明1"), 滑动=1
    )


def 制造资质证明2(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_all_seven`` → ``fabricate_seven_Swipe`` → ``fabricate_seven``。"""
    return _制造一件(
        ctx, IMG("Company/17.png", offset=(200, 0, 0, 0), delay=2000, desc="资质证明2"), 滑动=1
    )


def 制造高级申请(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_all_eight`` → ``fabricate_eight_Swipe`` →
    ``fabricate_eight_Swipe_2`` → ``fabricate_eight``。"""
    return _制造一件(ctx, IMG("Company/18.png", delay=2000, desc="高级制造申请"), 滑动=2)


def 制造2型钢材(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_all_nine`` → ``fabricate_nine_Swipe`` →
    ``fabricate_nine_Swipe_2`` → ``fabricate_nine``。"""
    return _制造一件(
        ctx, IMG("Company/19.png", offset=(200, 0, 0, 0), delay=2000, desc="2型钢材"), 滑动=2
    )


def 制造资质证明3(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_all_ten`` → ``fabricate_ten_Swipe`` →
    ``fabricate_ten_Swipe_2`` → ``fabricate_ten``。"""
    return _制造一件(
        ctx, IMG("Company/20.png", offset=(200, 0, 0, 0), delay=2000, desc="资质证明3"), 滑动=2
    )


def 退出制造(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_back``（旧 next：``[tea]``）。

    旧 ``post_delay`` 是 7000。
    """
    return ctx.tap(IMG("Collect/06.png", delay=7000, desc="退出制造台"))


def 制造已在主界面(ctx: TaskContext) -> bool:
    """旧节点 ``fabricate_convened``（旧 next：``[tea]``）。"""
    if not ctx.look(IMG("Startup/11.png", roi=(906, 340, 170, 205))):
        return False
    ctx.screen.sleep(3000)  # 旧 post_delay: 3000
    return True


#: 「社教模拟仪」四个 case → 对应的分支函数（旧 override 把
#: ``entry_dispath_three.next`` 换成 ``dispatch_social_one`` … ``dispatch_social_four``）。
社教档位: dict[str, Callable[[TaskContext], bool]] = {
    "初级社会指南": 选初级社会指南,
    "中级社会指南": 选中级社会指南,
    "高级社会指南": 选高级社会指南,
    "进阶社会指南": 选进阶社会指南,
}

#: 「制造物品」十个 case → 对应的分支函数（旧 override 把
#: ``entry_dispath_four.next`` 换成对应的 ``fabricate_all_*``）。
制造清单: dict[str, Callable[[TaskContext], bool]] = {
    "蓝色装备": 制造蓝色装备,
    "铜石墨条（蓝装升级）": 制造铜石墨条,
    "银石墨条（黄装升级）": 制造银石墨条,
    "100装备经验": 制造装备经验,
    "1型钢材": 制造1型钢材,
    "资质证明1": 制造资质证明1,
    "资质证明2": 制造资质证明2,
    "高级制造申请": 制造高级申请,
    "2型钢材": 制造2型钢材,
    "资质证明3": 制造资质证明3,
}


# ---------------------------------------------------------------------- 第五段：喝茶
# 旧 ``3_(5)_tea.json``。


def 喝茶(ctx: TaskContext) -> bool:
    """旧节点 ``tea``。

    旧 next 是 ``[entry_dispath_five, tearoom, tea_two, Instrument, tea_back,
    tea_convened, 异常处理]``；选项把它换成 ``"entry_dispath_five"``（喝茶）或
    ``["tea_back", "tea_convened"]``（不喝茶）。
    """
    ctx.step("派遣公司：喝茶")
    if ctx.text("是否喝茶", "喝茶") != "喝茶":
        return bool(
            ctx.scan(茶室退出, 茶室已在主界面, handle_exceptions, timeout=20_000, desc="跳过喝茶")
        )
    return bool(
        ctx.scan(茶室进门, 茶室退出, 茶室已在主界面, handle_exceptions, timeout=150_000, desc="喝茶")
    )


def 茶室进门(ctx: TaskContext) -> bool:
    """旧节点 ``entry_dispath_five``：点进派遣公司，再进茶室。

    旧 next：``[tearoom, tea_two, Instrument, 自己, tea_back, tea_convened,
    异常处理]``。
    """
    if not ctx.tap(派遣公司图标):
        return False
    return bool(
        ctx.scan(
            进茶室,
            选茶,
            摆茶具,
            茶室退出,
            茶室已在主界面,
            handle_exceptions,
            timeout=120_000,
            desc="茶室流程",
        )
    )


def 进茶室(ctx: TaskContext) -> bool:
    """旧节点 ``tearoom``：点「茶室」。

    旧 next：``[tea_two, Instrument, tearoom]``。
    """
    if not ctx.tap(OCR("茶室", roi=(965, 365, 155, 295), delay=2000, desc="进茶室")):
        return False
    return bool(ctx.scan(选茶, 摆茶具, timeout=30_000, desc="茶室"))


def 选茶(ctx: TaskContext) -> bool:
    """旧节点 ``tea_two``：点「茶」开始泡。

    旧 next：``[number, drink_tea, tea_two]`` —— 认出「次数」就说明今天的茶喝完了。
    """
    if not ctx.tap(OCR("茶", roi=(590, 145, 150, 140), delay=2000, desc="选茶")):
        return False
    return bool(ctx.scan(看次数, 倒茶, timeout=30_000, desc="泡茶"))


def 看次数(ctx: TaskContext) -> bool:
    """旧节点 ``number``（``DoNothing`` + ``post_delay`` 1000）：认出「次数」。

    旧 next：``[tea_home]``。
    """
    if not ctx.look(OCR("次数", desc="喝茶次数")):
        return False
    ctx.screen.sleep(1000)
    return 茶室回主页(ctx)


def 倒茶(ctx: TaskContext) -> bool:
    """旧节点 ``drink_tea``：点茶具倒茶（旧 ``target`` 是绝对点 (300,465)）。

    旧 next：``[company_confirm_one, drink_tea]``。
    """
    if not ctx.tap(
        IMG("Company/23.png", roi=(194, 0, 282, 214), point=(300, 465), delay=3000, desc="倒茶")
    ):
        return False
    return bool(ctx.scan(一级确认, timeout=30_000, desc="等确认按钮"))


def 一级确认(ctx: TaskContext) -> bool:
    """旧节点 ``company_confirm_one``：第一次「确认」。

    旧 next：``[lack, company_confirm_two_await]``。
    """
    if not ctx.tap(OCR("确认", roi=(90, 520, 625, 200), delay=2000, desc="确认（第一次）")):
        return False
    return bool(ctx.scan(缺少材料, 等待二次确认, timeout=30_000, desc="一次确认后"))


def 缺少材料(ctx: TaskContext) -> bool:
    """旧节点 ``lack``（``DoNothing`` + ``post_delay`` 3000）：认出「缺少」就收工。

    旧 next：``[tea_home]``。
    """
    if not ctx.look(OCR("缺少", desc="材料不足")):
        return False
    ctx.screen.sleep(3000)
    return 茶室回主页(ctx)


def 等待二次确认(ctx: TaskContext) -> bool:
    """旧节点 ``company_confirm_two_await``（``DoNothing`` + ``post_delay`` 13000）。

    旧 next：``[company_confirm_two, company_confirm_one]``。
    """
    ctx.screen.sleep(13000)
    return bool(ctx.scan(二级确认, 一级确认, timeout=30_000, desc="等第二次确认"))


def 二级确认(ctx: TaskContext) -> bool:
    """旧节点 ``company_confirm_two``：第二次「确认」。

    旧 next：``[Instrument, invite, company_confirm_two]``。
    """
    if not ctx.tap(OCR("确认", roi=(650, 230, 275, 260), delay=5000, desc="确认（第二次）")):
        return False
    return bool(ctx.scan(摆茶具, 邀请, timeout=30_000, desc="二次确认后"))


def 摆茶具(ctx: TaskContext) -> bool:
    """旧节点 ``Instrument``：点茶具（旧 JSON 里三张图任一，带 ``green_mask``）。

    旧 next：``[invite, Instrument]``。
    """
    if not _绿幕点(
        ctx,
        ["Company/24.png", "Company/25.png", "Company/26.png"],
        偏移=(-30, 100, 0, 0),
        说明="摆茶具",
    ):
        return False
    return bool(ctx.scan(邀请, timeout=30_000, desc="摆茶具后"))


def 邀请(ctx: TaskContext) -> bool:
    """旧节点 ``invite``：点「邀请」（旧 ``post_wait_freezes`` 是 1000）。

    旧 next：``[tea_click_one, invite]``。
    """
    if not ctx.tap(OCR("邀请", roi=(900, 500, 350, 200), wait_freezes=1000, desc="邀请品茗")):
        return False
    return bool(ctx.scan(品茗, timeout=30_000, desc="邀请后"))


def 品茗(ctx: TaskContext) -> bool:
    """旧节点 ``tea_click_one``：点「品茗」（旧 ``target`` 是绝对点 (1150,220)）。

    旧 next：``[topic, tea_click_one]``。
    """
    if not ctx.tap(
        OCR("品茗", roi=(5, 0, 150, 100), point=(1150, 220), delay=2000, desc="品茗")
    ):
        return False
    return bool(ctx.scan(展开话题, timeout=30_000, desc="品茗后"))


def 展开话题(ctx: TaskContext) -> bool:
    """旧节点 ``topic``（``DoNothing`` + ``post_delay`` 1000）：认出「展开的话题」。

    旧 next：``[tea_click_two, topic]``。

    注意：``origin`` 的旧 next 里又有 ``topic`` / ``tea_click_two`` 的回边，
    真照抄会变成函数之间无休止地互相递归。这里只在 ``结缘`` 保留「去感应」和
    「回去继续喝茶」两条去路，靠各自的 ``scan`` 超时兜底。
    """
    if not ctx.look(OCR("展开的话题", roi=(765, 35, 295, 85), desc="话题已展开")):
        return False
    ctx.screen.sleep(1000)
    return bool(ctx.scan(选话题, timeout=30_000, desc="展开话题后"))


def 选话题(ctx: TaskContext) -> bool:
    """旧节点 ``tea_click_two``：点最后一个话题（旧 JSON ``green_mask`` + ``index`` -1）。

    旧 next：``[origin, tea_click_two]``。
    """
    if not _绿幕点(
        ctx,
        "Company/27.png",
        roi=(865, 95, 310, 355),
        index=-1,
        偏移=(40, 0, 0, 0),
        delay=2000,
        说明="选话题",
    ):
        return False
    return bool(ctx.scan(结缘, timeout=30_000, desc="选话题后"))


def 结缘(ctx: TaskContext) -> bool:
    """旧节点 ``origin``：点「缘」结缘（旧 ``target_offset`` 是 (0,-370)）。

    旧 next：``[topic, tea_click_two, Go_to_Induction, origin, tea_two]``。
    头两条是回话题列表的回边（见 ``展开话题`` 的说明），这里保留后面两条去路。
    """
    if not ctx.tap(
        OCR("缘", roi=(165, 610, 125, 110), offset=(0, -370, 0, 0), delay=3000, desc="结缘")
    ):
        return False
    return bool(ctx.scan(去感应, 选茶, timeout=30_000, desc="结缘后"))


def 去感应(ctx: TaskContext) -> bool:
    """旧节点 ``Go_to_Induction``：点「感应」（旧 ``target_offset`` 是 (0,-290)）。

    旧 next：``[tea_two, tearoom, tea_home]``。
    """
    if not ctx.tap(OCR("感应", offset=(0, -290, 0, 0), delay=3000, desc="去感应")):
        return False
    return bool(ctx.scan(选茶, 进茶室, 茶室回主页, timeout=30_000, desc="感应后"))


def 茶室回主页(ctx: TaskContext) -> bool:
    """旧节点 ``tea_home``：点 ``Startup/10.png`` 回主页（旧 next：``[vitality]``）。"""
    return ctx.tap(IMG("Startup/10.png", delay=5000, desc="回主页"))


def 茶室退出(ctx: TaskContext) -> bool:
    """旧节点 ``tea_back``（旧 next：``[vitality]``）。

    旧 ``post_delay`` 是 7000。
    """
    return ctx.tap(IMG("Collect/06.png", delay=7000, desc="退出茶室"))


def 茶室已在主界面(ctx: TaskContext) -> bool:
    """旧节点 ``tea_convened``（旧 next：``[vitality]``）。"""
    if not ctx.look(IMG("Startup/11.png", roi=(906, 340, 170, 205))):
        return False
    ctx.screen.sleep(3000)  # 旧 post_delay: 3000
    return True


# ---------------------------------------------------------------- 第六段：活力值
# 旧 ``3_(6)_vitality.json``。


def 领取活力值(ctx: TaskContext) -> bool:
    """旧节点 ``vitality``。

    旧 next 是 ``[entry_dispath_six, vitality_one, vitality_back, vitality-convened,
    异常处理]``；选项把它换成 ``"entry_dispath_six"``（领取）或
    ``["vitality_back", "vitality-convened"]``（不领取）。
    """
    ctx.step("派遣公司：领取活力值")
    if ctx.text("是否领取活力值", "领取") != "领取":
        return bool(
            ctx.scan(活力退出, 活力已在主界面, handle_exceptions, timeout=20_000, desc="跳过活力值")
        )
    return bool(
        ctx.scan(
            进宿舍,
            点宿舍,
            活力退出,
            活力已在主界面,
            handle_exceptions,
            timeout=90_000,
            desc="领活力值",
        )
    )


def 进宿舍(ctx: TaskContext) -> bool:
    """旧节点 ``entry_dispath_six``：点进派遣公司，再进宿舍。

    旧 next：``[vitality_one, vitality_back, 异常处理]``。
    """
    if not ctx.tap(派遣公司图标):
        return False
    return bool(ctx.scan(点宿舍, 活力退出, handle_exceptions, timeout=60_000, desc="进宿舍"))


def 点宿舍(ctx: TaskContext) -> bool:
    """旧节点 ``vitality_one``：点「舍」。

    旧 next：``[vitality_two]``。
    """
    if not ctx.tap(OCR("舍", roi=(425, 435, 200, 230), delay=2000, desc="点宿舍")):
        return False
    return 点宿舍位(ctx)


def 点宿舍位(ctx: TaskContext) -> bool:
    """旧节点 ``vitality_two``：点宿舍空位（旧 ``target`` 是绝对点 (255,665)）。

    旧 next：``[vitality_three, vitality-visitor, vitality_home, vitality_two]``。
    """
    if not ctx.tap(IMG("Company/22.png", point=(255, 665), delay=5000, desc="点宿舍空位")):
        return False
    return bool(ctx.scan(只能提示, 点访客, 活力回主页, timeout=30_000, desc="宿舍空位"))


def 只能提示(ctx: TaskContext) -> bool:
    """旧节点 ``vitality_three``：点「只能」。

    旧 next：``[vitality_four]``。
    """
    if not ctx.tap(OCR("只能", delay=2000, desc="只能提示")):
        return False
    return 关闭提示(ctx)


def 关闭提示(ctx: TaskContext) -> bool:
    """旧节点 ``vitality_four``：点 ``Collect/04.png`` 关掉提示。

    旧 next：``[vitality-visitor, vitality_home]``。
    """
    if not ctx.tap(IMG("Collect/04.png", delay=2000, desc="关闭提示")):
        return False
    return bool(ctx.scan(点访客, 活力回主页, timeout=30_000, desc="关闭提示后"))


def 点访客(ctx: TaskContext) -> bool:
    """旧节点 ``vitality-visitor``：点「访客」。

    旧 next：``[vitality-get, vitality-visitor-quit, vitality-visitor]``。
    """
    if not ctx.tap(OCR("访客", delay=5000, desc="点访客")):
        return False
    return bool(ctx.scan(领活力, 访客退出, timeout=30_000, desc="访客"))


def 领活力(ctx: TaskContext) -> bool:
    """旧节点 ``vitality-get``：点「得」领活力值。

    旧 next：``[vitality-get, vitality-visitor-quit]``。
    """
    if not ctx.tap(OCR("得", delay=3000, desc="领取活力值")):
        return False
    return bool(ctx.scan(访客退出, timeout=20_000, desc="领活力收尾"))


def 访客退出(ctx: TaskContext) -> bool:
    """旧节点 ``vitality-visitor-quit``：点 ``Company/30.png`` 关访客面板。

    旧 next：``[vitality-visitor-quit, vitality_home, vitality_back]``。
    """
    if not ctx.tap(IMG("Company/30.png", delay=3000, desc="关掉访客面板")):
        return False
    return bool(ctx.scan(活力回主页, 活力退出, timeout=30_000, desc="访客收尾"))


def 活力回主页(ctx: TaskContext) -> bool:
    """旧节点 ``vitality_home``：点 ``Startup/10.png`` 回主页（旧节点没有 next）。"""
    return ctx.tap(IMG("Startup/10.png", desc="回主页"))


def 活力退出(ctx: TaskContext) -> bool:
    """旧节点 ``vitality_back``：点 ``Collect/06.png`` 退出（旧节点没有 next）。"""
    return ctx.tap(IMG("Collect/06.png", desc="退出活力值界面"))


def 活力已在主界面(ctx: TaskContext) -> bool:
    """旧节点 ``vitality-convened``（旧 ``post_delay`` 是 1000）。"""
    if not ctx.look(IMG("Startup/11.png", roi=(906, 340, 170, 205))):
        return False
    ctx.screen.sleep(1000)  # 旧 post_delay: 1000
    return True


# --------------------------------------------------------------------- 小工具


def _绿幕点(
    ctx: TaskContext,
    图,
    *,
    roi: Optional[tuple[int, int, int, int]] = None,
    偏移: Optional[tuple[int, int, int, int]] = None,
    delay: int = 0,
    index: int = 0,
    说明: str = "",
) -> bool:
    """旧 JSON 里带 ``green_mask`` / ``index`` 的模板节点专用的小工具。

    ``ctx.tap`` 走的是 ``Cand``，这两个参数传不进去，所以直接落到 ``ctx.screen``
    （``MWAScreen`` 是任务模块允许使用的两层之一）。
    """
    match = ctx.screen.find(图, roi=roi, green_mask=True, index=index)
    if not match:
        return False
    return ctx.screen.click(match, offset=偏移, delay=delay, desc=说明)
