"""Alcove 物华弥新小助手 —— 命令行入口。

    python main.py                      # 列出设备与任务，跑所有默认任务
    python main.py --list               # 只列设备与任务，不连接
    python main.py -t 启动 -t 邮箱       # 只跑指定任务（可重复）
    python main.py --all                # 跑注册表里的全部任务
    python main.py --device 0           # 指定第 0 个设备
    python main.py --gui                # 打开图形界面
    python main.py --selftest           # 自检：路径 / 资源 / OCR 模型，不连设备
    python main.py --debug              # 打开 maafw 的调试日志与截图

之前的版本要靠 MaaPiCli 的 interface.json 驱动，这里全部换成 Python 直连：
选设备 → 建控制器 → 加载图库与 OCR 模型 → 按顺序跑任务函数。

任务有两个来源，在 ``--list`` 里分成两组显示：
  · Python 实现（``PyPipeline/Tasks/*.py``）—— 新架构，纯 Python 控制流；
  · 旧流水线（``assets/resource_picli/base/pipeline/*.json``）—— 还没迁移的任务，
    由 ``MWATools.MWATaskPipeline`` 把 interface.json 的 option 合并成
    ``pipeline_override`` 后交给 maafw 原生执行。删掉对应 JSON、写好 Python
    模块，这个任务就会自动从「旧流水线」组消失。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 允许从任意目录运行：把项目根塞进 sys.path。
# 打包成 exe 之后 PyInstaller 已经接管了导入路径，这里跳过（冻结环境里
# __file__ 是合成路径，插进 sys.path 只会平白多一个不存在的目录）。
if not getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(__file__).resolve().parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

from MWATools.MWALogging import get_logger, setup_logging  # noqa: E402
from MWATools import MWAController, MWATask, MWATasker  # noqa: E402

logger = get_logger("main")


# ------------------------------------------------------------------ 参数

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alcove",
        description="物华弥新小助手（Alcove Python 版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-t", "--task", action="append", default=[],
                        metavar="任务名", help="要运行的任务（可重复指定）")
    parser.add_argument("--all", action="store_true", help="运行全部已注册任务")
    parser.add_argument("-l", "--list", action="store_true", help="只列设备与任务，不连接")
    parser.add_argument("-d", "--device", default=None, metavar="序号|地址",
                        help="选择设备：序号（0、1…）、序列号或窗口标题")
    parser.add_argument("-b", "--bundle", default=None, metavar="路径",
                        help="资源包路径（默认 assets/resource_picli/base）")
    parser.add_argument("--no-ocr", action="store_true", help="不加载 OCR 模型")
    parser.add_argument("--no-pipeline", action="store_true",
                        help="不加载旧 pipeline 节点表（只跑已迁移的 Python 任务时可用，启动更快）")
    parser.add_argument("--debug", action="store_true", help="开启 maafw 调试日志与存图")
    parser.add_argument("--gui", action="store_true", help="打开图形界面")
    parser.add_argument("--keep-error", action="store_true", help="任务失败也继续跑后面的")
    parser.add_argument("--selftest", action="store_true",
                        help="自检：不连设备，只检查路径/资源/OCR 模型是否装全了")
    parser.add_argument("-q", "--quiet", action="store_true", help="只写日志文件，不打屏幕")
    return parser


# ------------------------------------------------------------------ 展示

def show_targets() -> list:
    targets = MWAController.list_targets()
    if not targets:
        print("没有找到任何设备。")
        print("  · 安卓模拟器 / 真机：确认 adb 已连上（adb devices）")
        print("  · Windows 窗口：确认游戏窗口已经打开")
        return []

    print(f"找到 {len(targets)} 个可控制目标：")
    for index, target in enumerate(targets):
        print(f"  [{index}] {target.label}")
    return targets


def show_tasks() -> None:
    specs = MWATask.all_tasks()
    if not specs:
        print("没有注册任何任务。检查 PyPipeline/Tasks/ 下的模块是否能正常 import。")
        return

    legacy = MWATask.legacy_task_keys()
    python_specs = [s for s in specs if s.key not in legacy]

    groups: dict[str, list] = {}
    for spec in python_specs:
        groups.setdefault(spec.group, []).append(spec)

    print(f"已注册 {len(specs)} 个任务（Python 实现 {len(python_specs)} 个，"
          f"旧流水线 {len(legacy)} 个）：")
    for group, specs_in_group in groups.items():
        print(f"  ── {group} ──")
        for spec in specs_in_group:
            mark = "●" if spec.default_enabled else "○"
            print(f"  {mark} {spec.key:<12s} {spec.description}")

    if legacy:
        print(f"  ── {MWATask.LEGACY_GROUP} ──")
        for spec in specs:
            if spec.key in legacy:
                print(f"  ○ {spec.key:<12s} {spec.description}")
        total = len(legacy) + len(python_specs)
        print(f"  迁移进度：{len(python_specs)}/{total} 个任务已改成 Python 实现。")

    print("  （● = 默认运行。旧流水线任务要用到 pipeline JSON，"
          "别加 --no-pipeline。）")


# ------------------------------------------------------------------ 选设备

def pick_target(targets: list, wanted: str | None):
    if not targets:
        return None
    if wanted is None:
        return targets[0]

    if wanted.isdigit():
        index = int(wanted)
        if 0 <= index < len(targets):
            return targets[index]
        logger.error("设备序号 %s 超出范围（0~%d）", wanted, len(targets) - 1)
        return None

    for target in targets:
        if wanted in (target.name, getattr(target.device, "address", ""),
                      getattr(target.device, "window_name", "")):
            return target
    logger.error("找不到匹配 %r 的设备", wanted)
    return None


# ------------------------------------------------------------------ 主流程

def run_tasks(runner: MWATasker.MWATaskerClass, keys: list[str],
              *, stop_on_error: bool) -> bool:
    specs = MWATask.all_tasks()
    if not keys:
        keys = [spec.key for spec in specs if spec.default_enabled]
    if not keys:
        logger.warning("没有选中任何任务（可以在任务上用 default_enabled=True 设为默认）")
        return True

    task_runner = MWATask.TaskRunner(runner.screen)
    results = task_runner.run(keys, stop_on_error=stop_on_error)

    print()
    print("─── 运行结果 ───")
    ok = True
    for result in results:
        if result.skipped:
            state = "跳过"
        elif result.cancelled:
            state = "取消"
        elif result.success:
            state = "成功"
        else:
            state = "失败"
            ok = False
        extra = f"  {result.error}" if result.error else ""
        print(f"  {state}  {result.name}  ({result.elapsed:.1f}s){extra}")
    return ok


def _force_utf8_console() -> None:
    """把标准输出/错误切成 UTF-8。

    Windows 控制台默认是 GBK（cp936），日志里的中文一 print 就
    ``UnicodeEncodeError``。源码运行时还能靠 ``PYTHONUTF8=1`` 绕过去，打包成
    exe 之后就没人替用户设这个变量了，所以在程序里兜住。

    ``errors="replace"`` 是关键：终端字体不支持某个字时打问号，而不是崩掉。
    任何一步失败都直接放过 —— 拿不到可重配的流（比如被重定向到管道）是常事。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def selftest(args) -> int:
    """自检：不连设备，只确认这份程序（尤其是打包后的）装全了。

    打包产物最容易出问题的地方全在磁盘上 —— 只读/可写目录分家、OCR 模型没打进去、
    模板图库丢了、扫目录加载的模块没被 PyInstaller 收进去。这些都不需要连设备就能查，
    所以单独给个开关：装完先跑一次 ``Alcove --selftest``。
    """
    from MWATools import (  # noqa: PLC0415
        BUNDLE_ROOT,
        CONFIG_FILE,
        DEFAULT_BUNDLE,
        FROZEN,
        LOG_DIR,
        MWAResourceClass,
        USER_ROOT,
        interface_path,
        resolve_bundle_path,
    )

    problems: list[str] = []

    def check(ok: bool, text: str) -> None:
        print(f"  {'✓' if ok else '✗'} {text}")
        if not ok:
            problems.append(text)

    print("─── 路径 ───")
    print(f"  运行形态：{'打包产物（frozen）' if FROZEN else '源码'}")
    print(f"  只读根 BUNDLE_ROOT：{BUNDLE_ROOT}")
    print(f"  可写根 USER_ROOT  ：{USER_ROOT}")
    print(f"  日志目录          ：{LOG_DIR}")
    print(f"  配置缓存          ：{CONFIG_FILE}")
    print()

    print("─── 可写性 ───")
    probe = USER_ROOT / ".alcove_write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        check(True, f"USER_ROOT 可写：{USER_ROOT}")
    except OSError as exc:
        check(False, f"USER_ROOT 不可写（{exc}）—— 日志和 config.json 会写不进去")
    print()

    print("─── 资源 ───")
    iface = interface_path()
    print(f"  interface.json：{iface}")
    check(iface.is_file(), "interface.json 存在")

    bundle = resolve_bundle_path(args.bundle or DEFAULT_BUNDLE, BUNDLE_ROOT)
    print(f"  资源包        ：{bundle}")
    image_dir = bundle / "image"
    pngs = sorted(image_dir.rglob("*.png")) if image_dir.is_dir() else []
    check(bool(pngs), f"模板图库：{len(pngs)} 张 png")

    ocr_dir = bundle / "model" / "ocr"
    for name in ("det.onnx", "rec.onnx", "keys.txt"):
        target = ocr_dir / name
        size = target.stat().st_size if target.is_file() else 0
        check(size > 0, f"OCR {name}：{size} 字节（目录 {ocr_dir}）")
    print()

    print("─── 真的加载一遍（不需要设备）───")
    resource = MWAResourceClass()
    try:
        ok = resource.load(bundle, with_ocr=not args.no_ocr,
                           with_pipeline=not args.no_pipeline)
    except Exception as exc:  # noqa: BLE001 - 自检就是要把异常显示出来
        check(False, f"资源加载抛异常：{exc}")
        ok = False
    else:
        check(ok, "模板图库 + OCR 模型 + 自定义扩展都挂上了")
    check(bool(resource.resource.loaded), "maa 那边报告 Resource 已加载")
    print()

    print("─── 任务注册 ───")
    specs = MWATask.all_tasks()
    legacy = MWATask.legacy_task_keys()
    check(len(specs) >= 19,
          f"注册任务 {len(specs)} 个（Python 实现 {len(specs) - len(legacy)} 个，"
          f"旧流水线 {len(legacy)} 个）")
    print()

    if problems:
        print(f"自检发现 {len(problems)} 个问题：")
        for item in problems:
            print(f"  · {item}")
        print("  排错对照见 docs/打包说明.md。")
        return 1
    print("自检通过。")
    return 0


def main(argv: list[str] | None = None) -> int:
    _force_utf8_console()
    args = build_parser().parse_args(argv)

    setup_logging(to_file=not args.quiet, console=not args.quiet)

    # 任务模块：导入即注册
    from PyPipeline import Tasks  # noqa: PLC0415

    Tasks.load_all()

    if args.selftest:
        return selftest(args)

    if args.gui:
        return launch_gui(args)

    if args.list:
        show_targets()
        print()
        show_tasks()
        return 0

    show_tasks()
    print()

    targets = show_targets()
    target = pick_target(targets, args.device)
    if target is None:
        return 1

    runner = MWATasker.MWATaskerClass()
    print()
    print(f"正在连接 {target.label} …")
    if not runner.start(target, args.bundle,
                        with_ocr=not args.no_ocr,
                        with_pipeline=not args.no_pipeline,
                        debug=args.debug):
        logger.error("连接或初始化失败，退出")
        return 1

    for line in runner.info().items():
        logger.info("%s = %s", *line)

    try:
        ok = run_tasks(runner, list(args.task), stop_on_error=not args.keep_error)
    except KeyboardInterrupt:
        print()
        logger.warning("已中断")
        return 130
    finally:
        runner.stop()

    return 0 if ok else 1


def launch_gui(args) -> int:
    try:
        from MWAGui.app import run as run_gui  # noqa: PLC0415
    except ImportError as exc:
        logger.error("打不开图形界面：%s", exc)
        logger.error("安装 GUI 依赖试试：uv add flet   或   pip install flet")
        return 1
    return run_gui(bundle=args.bundle, device=args.device, debug=args.debug,
                   with_pipeline=not args.no_pipeline)


if __name__ == "__main__":
    sys.exit(main())
