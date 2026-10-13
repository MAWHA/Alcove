"""启动游戏 —— 对应旧 ``pipeline/1_startup.json``。

旧 JSON 是一张有向图：``next`` 里的节点按顺序试探，第一个命中的被执行，
然后顺着它自己的 ``next`` 继续走，直到超时。那张图能跑，但读起来像迷宫。

这里改成直白的 Python：**"先把屏幕上可能出现的弹窗都点掉，再冷启动游戏，
然后一直等到主界面出现"**。行为与旧图等价，但读代码的人能一眼看明白。

旧图的每一段都有对应关系，注释里标了原始节点名，方便对照回退。
"""

from __future__ import annotations

import time

from MWATools.MWATask import TaskContext, task

# ---------------------------------------------------------------- 常量

GAME_PACKAGE = "com.cipaishe.wuhua.bilibili"

# 旧 JSON 里 startup 节点的 package 带上了 SplashActivity，
# 直接用 am start 拉起这个 Activity 比 monkey 可靠。
GAME_ACTIVITY = f"{GAME_PACKAGE}/com.cipaishe.wuhua.bilibili.activity.ONESDKSplashActivity"

# roi 原样照抄旧 JSON —— 基准分辨率 1280x720（maafw 会自动缩放到实际屏幕）
ROI_健康 = (405, 230, 510, 260)
ROI_加载中 = (195, 595, 260, 125)
ROI_更新 = (403, 249, 474, 111)
ROI_公告 = (360, 50, 545, 105)
ROI_公告关闭按钮 = (1063, 27, 197, 157)
ROI_防沉迷 = (198, 618, 125, 62)
ROI_今日登录提示 = (115, 590, 277, 100)
ROI_上新 = (316, 390, 711, 296)
ROI_主界面标记 = (906, 340, 170, 205)

# 旧 start-serve 节点的 OCR 词表：这七个词任意一个出现都说明还在加载/更新
词表_加载中 = ["服务", "同步", "更新", "解压", "检测", "资源", "配置"]


# ---------------------------------------------------------------- 单步动作
# 每个函数对应旧图里的一个节点，命中返回 True、没命中返回 False。


def 有健康忠告(ctx: TaskContext) -> bool:
    """旧 ``start-healthy``：开屏的"健康游戏忠告"，点掉它。"""
    match = ctx.screen.text("健康", roi=ROI_健康)
    if not match:
        return False
    ctx.screen.click(match, delay=3000, desc="关闭健康忠告")
    return True


def 点掉防沉迷提示(ctx: TaskContext) -> bool:
    """旧 ``start-accessing``：进服时的实名/防沉迷提示。

    旧 JSON 用 ``target_offset: [0, -40, 0, 0]`` 把点击位置从文字框上移 40px。
    """
    match = ctx.screen.text("抵制不良", roi=ROI_防沉迷)
    if not match:
        return False
    ctx.screen.click(match, offset=(0, -40, 0, 0), wait_freezes=7000,
                     desc="同意防沉迷提示")
    return True


def 关闭公告(ctx: TaskContext) -> bool:
    """旧 ``start-announcement`` + ``start-CloseAnnouncement``。

    先等公告栏的标题出现，再找关闭按钮点掉。
    """
    if not ctx.screen.text("公告", roi=ROI_公告):
        return False
    ctx.screen.sleep(1000)
    return ctx.retry(
        lambda: ctx.find_then_click("Startup/12.png", roi=ROI_公告关闭按钮, delay=2000),
        timeout=8000,
        interval=500,
        desc="关闭公告",
    )


def 点更新(ctx: TaskContext) -> bool:
    """旧 ``start-update``：热更新按钮，旧 JSON 直接点死坐标 (765,430)。"""
    match = ctx.screen.text("更新", roi=ROI_更新)
    if not match:
        return False
    ctx.screen.click((765, 430), delay=3000, desc="点更新")
    return True


def 还在加载(ctx: TaskContext) -> bool:
    """旧 ``start-serve``：加载/解压/同步画面。旧图里是 DoNothing，即只等。"""
    match = ctx.screen.text(词表_加载中, roi=ROI_加载中)
    if not match:
        return False
    ctx.step(f"游戏加载中（{match.text}）")
    return True


def 点掉今日登录提示(ctx: TaskContext) -> bool:
    """旧 ``start-handling-remind``：登录后的"今日不再提示"弹窗。"""
    if not ctx.screen.text("今日登录不再提示", roi=ROI_今日登录提示):
        return False
    # 旧 JSON 的 target 是死坐标 (1160,130)，不是识别框
    ctx.screen.click((1160, 130), delay=2000, desc="关闭今日登录提示")
    return True


def 点掉上新(ctx: TaskContext) -> bool:
    """旧 ``start-up-new``：衣装/周边上新弹窗。"""
    match = ctx.screen.text(["衣装上新", "周边上新"], roi=ROI_上新)
    if not match:
        return False
    ctx.screen.click((1160, 130), delay=2000, desc="关闭上新弹窗")
    return True


def 在主界面(ctx: TaskContext) -> bool:
    """旧 ``start-convened``：主界面左上角的固定标记。

    这是整条启动链的终点 —— 旧图里它没有 ``next``，即"到这里算完"。
    """
    return ctx.screen.find("Startup/11.png", roi=ROI_主界面标记).hit


# ---------------------------------------------------------------- 启动流程


def _扫一遍启动画面(ctx: TaskContext) -> bool:
    """处理一个启动画面上的弹窗，处理掉返回 True。

    顺序按旧图 ``next`` 的排列：公告 → 主界面 → 防沉迷 → 加载中 → 更新 …
    最常用的路径放在前面，省时间。
    """
    if 关闭公告(ctx):
        return True
    if 在主界面(ctx):
        return True
    if 有健康忠告(ctx):
        return True
    if 点掉防沉迷提示(ctx):
        return True
    if 点更新(ctx):
        return True
    if 点掉今日登录提示(ctx):
        return True
    if 点掉上新(ctx):
        return True
    return False


@task(
    "启动",
    "启动游戏",
    group="基础",
    description="打开游戏并一路点掉各种弹窗，直到出现主界面",
    order=10,
    default_enabled=True,
)
def 启动(ctx: TaskContext) -> bool:
    """对应旧 ``1_startup.json`` 的 ``Start`` 节点（含它的整个 next 链）。"""
    screen = ctx.screen

    # 旧 Start 节点是 DirectHit + post_delay 5000：先给游戏一点时间
    screen.sleep(5000)
    ctx.check_cancel()

    # 已经坐在游戏里了就直接结束
    if 在主界面(ctx):
        ctx.step("已经在主界面")
        return True

    # 先扫一遍：可能刚切回来就停在某个弹窗上
    for _ in range(6):
        ctx.check_cancel()
        if 在主界面(ctx):
            ctx.step("已经在主界面")
            return True
        if not _扫一遍启动画面(ctx):
            break

    # 还在加载就等它加载完（旧图里 start-serve 的 timeout 是 120 秒）
    if 还在加载(ctx):
        ctx.step("等待游戏加载完成")
        ctx.wait_for(lambda: not 还在加载(ctx), timeout=120_000, interval=3000)

    if 在主界面(ctx):
        return True

    # 到这一步说明游戏没在跑，冷启动它
    ctx.step("启动游戏")
    screen.start_app(GAME_ACTIVITY, wait_freezes=10000)

    # 旧 startup 节点的 timeout 是 120000：最多等两分钟进主界面
    ctx.step("等待进入游戏")
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        ctx.check_cancel()
        if 在主界面(ctx):
            ctx.step("已进入主界面")
            return True
        if _扫一遍启动画面(ctx):
            continue
        if 还在加载(ctx):
            screen.sleep(3000)
            continue
        screen.sleep(2000)

    ctx.log.warning("等待进入游戏超时（120 秒）")
    return False


@task(
    "关闭游戏",
    "关闭游戏",
    group="基础",
    description="强制结束游戏进程",
    order=900,
)
def 关闭游戏(ctx: TaskContext) -> bool:
    """对应旧 ``1_startup.json`` 的 ``StopApp`` 节点。"""
    ctx.step("关闭游戏")
    ctx.screen.stop_app(GAME_PACKAGE)
    return True
