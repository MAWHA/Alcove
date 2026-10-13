"""Tasker 组装：把 Resource / Controller / Tasker / Screen 拼成一个可用的运行时。

对应旧版的 ``MWATaskerClass`` + ``MWATaskerBind``，但：
* 控制器与资源包都是显式传进来的，不再有隐式的全局状态；
* ``bind()`` 的返回值会被检查（旧版直接忽略，绑不上也照样往下跑）；
* 连接失败会抛出带原因的错误，而不是被裸 ``except:`` 吞掉。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

from maa.controller import Controller
from maa.tasker import Tasker

from .MWAController import Target, create_controller
from .MWALogging import get_logger
from .MWAPaths import LOG_DIR, PROJECT_ROOT
from .MWAResource import DEFAULT_BUNDLE, MWAResourceClass, resolve_bundle_path
from .MWAScreen import BASE_SIZE, Screen

__all__ = ["MWATaskerClass"]

logger = get_logger("运行时")


class MWATaskerClass:
    """一次自动化会话的全部底层对象。"""

    def __init__(self, user_path: Union[str, Path, None] = None) -> None:
        self.user_path = Path(user_path) if user_path else PROJECT_ROOT
        self.resource: Optional[MWAResourceClass] = None
        self.controller: Optional[Controller] = None
        self.tasker: Optional[Tasker] = None
        self.screen: Optional[Screen] = None
        self.target: Optional[Target] = None
        self._configured = False

    # ------------------------------------------------------------------ 静态设置

    def _configure_tasker(self, *, debug: bool = False) -> None:
        """全局设置必须在创建 Tasker / 加载资源之前完成。"""
        if self._configured:
            return
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            Tasker.set_log_dir(str(LOG_DIR / "maa"))
            Tasker.set_save_draw(debug)
            from maa.define import LoggingLevelEnum

            Tasker.set_stdout_level(
                LoggingLevelEnum.Debug if debug else LoggingLevelEnum.Warn
            )
        except Exception as exc:  # 设置失败不该阻断运行
            logger.warning("Tasker 全局设置失败：%s", exc)
        self._configured = True

    # ------------------------------------------------------------------ 组装

    def connect(self, target: Target) -> bool:
        """创建并连接控制器。"""
        self.controller = create_controller(target)
        self.target = target
        job = self.controller.post_connection()
        if not job.wait().succeeded:
            raise RuntimeError(f"连接失败：{target.label}")
        if not self.controller.connected:
            raise RuntimeError(f"连接后状态异常：{target.label}")
        logger.info("已连接：%s", target.label)
        return True

    def load_resource(
        self,
        bundle: Union[str, Path, None] = None,
        *,
        bundle_base: Optional[Path] = None,
        with_ocr: bool = True,
        with_pipeline: bool = False,
        with_custom: bool = True,
    ) -> bool:
        """加载资源包（图库 + OCR 模型；可选加载旧 pipeline）。

        ``with_pipeline=True`` 会额外加载 ``pipeline/`` —— 只有还要跑
        「旧流水线任务」（``MWATask.register_legacy_tasks`` 注册的那些）才需要。
        """
        if bundle is None:
            bundle = self.user_path / DEFAULT_BUNDLE
        else:
            bundle = resolve_bundle_path(bundle, bundle_base or self.user_path)
        self.resource = MWAResourceClass(bundle)
        return self.resource.load(
            bundle, with_ocr=with_ocr, with_pipeline=with_pipeline, with_custom=with_custom
        )

    def bind(self) -> bool:
        """创建 Tasker 并绑定资源与控制器。"""
        if self.resource is None:
            raise RuntimeError("尚未加载资源包")
        if self.controller is None:
            raise RuntimeError("尚未连接控制器")

        self.tasker = Tasker()
        # 注意：maafw 的 bind 是 `resource and controller` 短路，
        # 资源绑定失败时控制器会静默不绑，所以两个都要单独确认。
        if not self.tasker.bind(self.resource.resource, self.controller):
            raise RuntimeError("Tasker.bind 失败")
        if not self.tasker.inited:
            raise RuntimeError("Tasker 未初始化完成")

        adb = None
        if self.target is not None and self.target.kind == "adb":
            adb = (self.target.device.adb_path, self.target.device.address)
        self.screen = Screen(self.tasker, self.controller, adb=adb)
        logger.info("运行时就绪（基准分辨率 %dx%d）", *BASE_SIZE)
        return True

    def start(
        self,
        target: Target,
        bundle: Union[str, Path, None] = None,
        *,
        bundle_base: Optional[Path] = None,
        with_ocr: bool = True,
        with_pipeline: bool = False,
        with_custom: bool = True,
        debug: bool = False,
    ) -> bool:
        """一步到位：连接 → 加载资源 → 绑定。"""
        self._configure_tasker(debug=debug)
        self.connect(target)
        self.load_resource(
            bundle,
            bundle_base=bundle_base,
            with_ocr=with_ocr,
            with_pipeline=with_pipeline,
            with_custom=with_custom,
        )
        self.bind()
        return True

    # ------------------------------------------------------------------ 状态

    @property
    def ready(self) -> bool:
        return bool(
            self.tasker
            and self.tasker.inited
            and self.screen is not None
            and self.controller is not None
            and self.controller.connected
        )

    def info(self) -> dict[str, Any]:
        """给 GUI 显示的状态摘要。"""
        data: dict[str, Any] = {"ready": self.ready}
        if self.target:
            data["target"] = self.target.label
            data["target_kind"] = self.target.kind
        if self.controller is not None:
            try:
                data["connected"] = bool(self.controller.connected)
                data["uuid"] = str(self.controller.uuid)
                data["resolution"] = tuple(self.controller.resolution)
            except Exception:
                pass
        if self.resource is not None and self.resource.bundle:
            data["bundle"] = str(self.resource.bundle)
            data["resource_loaded"] = self.resource.loaded
        return data

    def stop(self) -> None:
        """中断当前任务（不销毁对象）。"""
        if self.tasker is not None:
            try:
                self.tasker.post_stop().wait()
            except Exception:
                logger.debug("post_stop 失败", exc_info=True)

    def clear_cache(self) -> None:
        if self.tasker is not None:
            self.tasker.clear_cache()

    # ================================================================== 旧接口兼容
    #
    # 上游的 ``main.py`` / ``test.py`` / ``MWATools/adbcs.py`` 用的是
    # ``MWATaskerClass`` 那套接口（``MWATaskerBind`` / ``run_action`` /
    # ``run_custom_recognition``，属性 ``Tasker``）。下面这组薄壳让它们继续能跑。

    @property
    def Tasker(self) -> Optional[Tasker]:
        """旧属性名（新代码请用 ``tasker``）。"""
        return self.tasker

    @property
    def UserPath(self) -> Path:
        """旧属性名（新代码请用 ``user_path``）。"""
        return self.user_path

    def MWATaskerBind(self, resource: Any, controller: Any) -> bool:
        """旧接口：把 maa 的 ``Resource`` + ``Controller`` 绑到一个新 Tasker 上。

        ``resource`` 既可以是 ``MWAResourceClass``，也可以是它内部那个
        maa ``Resource``（上游两处调用分别传了这两种）。
        """
        self._configure_tasker()
        if isinstance(resource, MWAResourceClass):
            self.resource = resource
            maa_resource = resource.resource
        else:
            self.resource = None
            maa_resource = resource
        self.controller = controller
        self.tasker = Tasker()
        if not self.tasker.bind(maa_resource, controller):
            raise RuntimeError("Tasker.bind 失败")
        self.screen = Screen(self.tasker, controller, adb=None)
        return True

    def run_action(self, entry: str, pipeline_override: dict[str, Any] | None = None):
        """旧接口：跑一个流水线任务并等它结束。"""
        if self.tasker is None:
            raise RuntimeError("尚未绑定 Tasker，先调用 bind() 或 MWATaskerBind()")
        return self.tasker.post_task(entry, pipeline_override or {}).wait().get()

    def run_custom_action(self, action_name: str, action_param: Any = None):
        """旧接口占位（上游原实现就是 ``pass``）。"""
        return None

    def run_custom_recognition(
        self, entry: str, pipeline_override: dict[str, Any] | None = None
    ):
        """旧接口：跑一个自定义识别（实现上同样是 post_task + 等待）。"""
        if self.tasker is None:
            raise RuntimeError("尚未绑定 Tasker，先调用 bind() 或 MWATaskerBind()")
        return self.tasker.post_task(entry, pipeline_override or {}).wait().get()
