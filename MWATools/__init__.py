"""MWATools —— Alcove 的 maafw 封装层。

分层：

* ``MWAPaths``      路径解析（绝不依赖 CWD）
* ``MWALogging``    日志与事件总线（GUI 靠它拿实时进度）
* ``MWAController`` 设备发现 / 控制器创建
* ``MWAResource``   资源包加载（只加载图库与 OCR 模型，不加载 pipeline）
* ``MWAScreen``     同步的「眼睛与手」—— 识别与动作
* ``MWATasker``     运行时组装
* ``MWATask``       任务注册表 / 上下文 / 执行器
* ``MWAInterface``  interface.json 读取（仅兼容用）

典型用法：

    from MWATools import MWATaskerClass, list_targets, TaskRunner

    targets = list_targets()
    runtime = MWATaskerClass()
    runtime.start(targets[0])
    TaskRunner(runtime.screen).run(["启动", "邮箱"])
"""

from .MWAController import (
    Target,
    create_controller,
    init_toolkit,
    list_adb_devices,
    list_targets,
    list_windows,
)
from .MWAInterface import ProjectInterface, load_interface
from .MWALogging import Events, events, get_logger, install_gui_handler, setup_logging
from .MWAPaths import (
    ASSETS_DIR,
    BUNDLE_ROOT,
    CONFIG_FILE,
    FROZEN,
    LOG_DIR,
    PROJECT_ROOT,
    USER_ROOT,
    interface_path,
)
from .MWAResource import DEFAULT_BUNDLE, MWAResourceClass, resolve_bundle_path
from .MWAScreen import BASE_SIZE, Match, Screen
from .MWATask import (
    Choice,
    Option,
    TaskCancelled,
    TaskContext,
    TaskFailed,
    TaskResult,
    TaskRunner,
    TaskSpec,
    all_tasks,
    get_task,
    register,
    registry,
    task,
)
from .MWATasker import MWATaskerClass

__all__ = [
    # 路径 / 日志
    "FROZEN", "BUNDLE_ROOT", "USER_ROOT",
    "PROJECT_ROOT", "ASSETS_DIR", "CONFIG_FILE", "LOG_DIR", "interface_path",
    "setup_logging", "get_logger", "install_gui_handler", "events", "Events",
    # 控制器
    "Target", "init_toolkit", "list_adb_devices", "list_windows", "list_targets",
    "create_controller",
    # 资源 / 屏幕 / 运行时
    "DEFAULT_BUNDLE", "MWAResourceClass", "resolve_bundle_path",
    "BASE_SIZE", "Match", "Screen",
    "MWATaskerClass",
    # 任务
    "Choice", "Option", "TaskSpec", "TaskContext", "TaskRunner", "TaskResult",
    "TaskCancelled", "TaskFailed",
    "task", "register", "registry", "get_task", "all_tasks",
    # interface.json（兼容）
    "ProjectInterface", "load_interface",
]
