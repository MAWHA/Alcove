"""设备发现与控制器创建。

取代旧版 ``MWAControllerClass``：旧版只会取 ``interface["controller"][0]["name"]``
再猜一个设备，而且 ``except:`` 裸吞异常。这里把「发现」和「连接」分开，
让 GUI 能列出设备让用户自己挑，也能把错误如实报出来。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Union

from maa.controller import AdbController, Controller, Win32Controller
from maa.toolkit import AdbDevice, DesktopWindow, Toolkit

from .MWALogging import get_logger
from .MWAPaths import PROJECT_ROOT

__all__ = [
    "Target",
    "MWAControllerClass",
    "init_toolkit",
    "list_adb_devices",
    "list_windows",
    "list_targets",
    "create_controller",
]

logger = get_logger("控制器")

_initialized = False


def init_toolkit() -> bool:
    """初始化 MaaToolkit，只做一次。必须在发现设备之前调用。"""
    global _initialized
    if _initialized:
        return True
    ok = bool(Toolkit.init_option(str(PROJECT_ROOT)))
    if not ok:
        logger.error("Toolkit.init_option 失败，路径：%s", PROJECT_ROOT)
    _initialized = True
    return ok


@dataclass
class Target:
    """一个可连接的运行目标（安卓设备 / 桌面窗口）。"""

    kind: str                       # "adb" | "win32"
    name: str
    device: Union[AdbDevice, DesktopWindow, None] = None
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.label


def list_adb_devices() -> list[Target]:
    init_toolkit()
    out: list[Target] = []
    for device in Toolkit.find_adb_devices():
        label = f"{device.name} ({device.address})" if device.name else str(device.address)
        out.append(
            Target(
                kind="adb",
                name=label,
                device=device,
                info={"address": device.address, "adb_path": str(device.adb_path)},
            )
        )
    logger.info("发现 %d 个 ADB 设备", len(out))
    return out


def list_windows() -> list[Target]:
    """列出桌面窗口（Windows 上才有效）。"""
    init_toolkit()
    out: list[Target] = []
    try:
        windows = Toolkit.find_desktop_windows()
    except Exception as exc:  # 非 Windows 平台直接不可用
        logger.debug("列举桌面窗口失败：%s", exc)
        return out
    for window in windows:
        title = window.window_name or window.class_name or "<无标题>"
        out.append(
            Target(
                kind="win32",
                name=title,
                device=window,
                info={"class_name": window.class_name},
            )
        )
    logger.info("发现 %d 个桌面窗口", len(out))
    return out


def list_targets(kinds: tuple[str, ...] = ("adb", "win32")) -> list[Target]:
    targets: list[Target] = []
    if "adb" in kinds:
        targets += list_adb_devices()
    if "win32" in kinds:
        targets += list_windows()
    return targets


def create_controller(target: Target) -> Controller:
    """按目标类型创建控制器对象（**尚未连接**）。"""
    if target.kind == "adb":
        device = target.device
        if not isinstance(device, AdbDevice):
            raise ValueError("ADB 目标缺少设备信息，请重新枚举设备")
        logger.info("创建 ADB 控制器：%s @ %s", device.name, device.address)
        # screencap_methods / input_methods 直接沿用 Toolkit 探测结果：
        # maafw 会在连接时自动挑最快可用的一种，不需要我们手工指定。
        return AdbController(
            adb_path=str(device.adb_path),
            address=device.address,
            screencap_methods=device.screencap_methods,
            input_methods=device.input_methods,
            config=device.config,
        )

    if target.kind == "win32":
        window = target.device
        if not isinstance(window, DesktopWindow):
            raise ValueError("窗口目标缺少句柄，请重新枚举窗口")
        logger.info("创建 Win32 控制器：%s", window.window_name)
        return Win32Controller(window.hwnd)

    raise ValueError(f"不支持的控制器类型：{target.kind}")


# ====================================================================== 旧接口兼容
#
# 上游的 ``main.py`` / ``test.py`` / ``MWATools/adbcs.py`` 用的是
# ``MWAControllerClass`` 这套类接口（``load_controller`` / ``choose_adb_controller``
# / ``connect_adb_controller``）。新架构换成了上面的模块级函数 + ``Target``，
# 但为了不让上游那些文件失效，这里保留一个薄壳，行为与原实现一致。


class MWAControllerClass:
    """``MWAControllerClass`` 的兼容壳（上游仍在使用这一名字）。"""

    def __init__(self) -> None:
        # 延后导入：``interface`` 一旦求值就会读 interface.json（旧版是导入即读）。
        from .MWAInterface import interface

        self._controller_config = interface["controller"][0]
        self.adb_controllers: list[AdbDevice] = []
        self.desktop_controllers: list[DesktopWindow] = []
        self.adb_controller: Optional[AdbDevice] = None

    def load_controller(self):
        """按 ``interface.json`` 里 ``controller[0].name`` 枚举设备。"""
        if self._controller_config["name"] == "安卓端":
            self.adb_controllers = list(Toolkit.find_adb_devices())
            logger.info("Alcove搜索到了%d个设备", len(self.adb_controllers))
            return self.adb_controllers
        if self._controller_config["name"] == "win32端":
            self.desktop_controllers = list(Toolkit.find_desktop_windows())
            logger.info("Alcove搜索到了%d个设备", len(self.desktop_controllers))
            return self.desktop_controllers
        return None

    def find_adb_controller(self, adb_path, address):
        """按 adb_path 或 address 找到设备并选中（配合 Alcove_config.yaml）。"""
        self.adb_controllers = list(Toolkit.find_adb_devices())
        for device in self.adb_controllers:
            if device.adb_path == adb_path or device.address == address:
                # TODO: adb_path 和 address 暂时没有都匹配
                self.choose_adb_controller(device_index=self.adb_controllers.index(device))
                logger.info("从Alcove_config.yaml中读取到%r这个设备并连接", (adb_path, address))
                return device
        return None

    def choose_adb_controller(self, device_index=0):
        """选择 adb 控制器。"""
        if len(self.adb_controllers) > 0:
            self.adb_controller = self.adb_controllers[device_index]
            logger.info(
                "选择了%r这个设备",
                (self.adb_controller.name, self.adb_controller.address),
            )
            return self.adb_controller
        logger.error("未搜索到adb设备!")
        return None

    def connect_adb_controller(self) -> Optional[Controller]:
        """连接已选中的 adb 控制器。"""
        device = self.adb_controller
        if device is None:
            logger.error("还没选设备，先调用 choose_adb_controller()")
            return None
        adb_controller = AdbController(
            adb_path=str(device.adb_path),
            screencap_methods=device.screencap_methods,
            address=device.address,
            input_methods=device.input_methods,
            config=device.config,
        )
        try:
            adb_controller.post_connection().wait()
            logger.info("已连接到模拟器:%s", adb_controller)
        except Exception as exc:  # noqa: BLE001 - 旧实现也是吞掉异常
            logger.error("模拟器连接失败:%s（%s）", adb_controller, exc)
        return adb_controller

    def choose_desktop_controller(self, device_index=0):
        pass

    def connect_desktop_controller(self):
        pass
