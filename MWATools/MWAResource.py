"""资源包加载。

与旧版的区别（这是新架构的关键决定）：

旧版 ``Resource().post_bundle(path)`` 会把 ``pipeline/``、``image/``、``model/``
一股脑加载进来，整个流程因此被 pipeline JSON 绑定。
新架构默认只用得到两样东西：

* ``image/``       —— 模板匹配的图库
* ``model/ocr/``   —— OCR 模型

所以这里**默认只加载这两样**，不碰 ``pipeline/*.json``；Python 任务模块与
老 JSON 之间因此没有耦合，老 JSON 可以逐个废弃。

**过渡期例外**：``assets/resource_picli/base/pipeline/`` 下还有一大部分任务
没迁完，这些任务靠 ``MWATask.register_legacy_tasks`` 注册成「旧流水线任务」，
它们**需要** pipeline 被加载。所以 ``load(..., with_pipeline=True)`` 会额外
把 ``pipeline/`` 也加载进来。等迁移做完，这个开关就可以关掉（甚至删掉）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from maa.resource import Resource

from .MWACustomAction import actions
from .MWALogging import get_logger

__all__ = ["MWAResourceClass", "resolve_bundle_path", "DEFAULT_BUNDLE"]

logger = get_logger("资源")

#: 当前使用的资源包（相对项目根）。对应 interface.json 里 resource[].path 指向的那套。
DEFAULT_BUNDLE = "assets/resource_picli/base"


def resolve_bundle_path(path: Union[str, Path], base_dir: Path) -> Path:
    """把资源包路径解析成绝对路径。

    兼容两种写法：
      * 相对路径 —— 相对 **interface.json 所在目录**（ProjectInterface v2 的语义）
      * 绝对路径 —— 原样使用
    """
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


class MWAResourceClass:
    """资源包管理器。"""

    def __init__(self, bundle: Union[str, Path, None] = None) -> None:
        self.resource = Resource()
        self.bundle: Union[Path, None] = None
        self._loaded = False
        if bundle is not None:
            self.bundle = Path(bundle)

    # ------------------------------------------------------------------ 加载

    def load(
        self,
        bundle: Union[str, Path, None] = None,
        *,
        with_ocr: bool = True,
        with_pipeline: bool = False,
        with_custom: bool = True,
    ) -> bool:
        """加载资源包。

        Args:
            bundle: 资源包根目录（含 ``image/``、``model/``、``pipeline/``）。
            with_ocr: 是否加载 ``model/ocr/``。
            with_pipeline: 是否**额外**加载 ``pipeline/``。只有还在跑
                「旧流水线任务」时才需要（见 ``MWATask.register_legacy_tasks``）。
            with_custom: 是否把 ``PyPipeline/CustomActions/`` 下发现的自定义
                动作/识别挂到 Resource 上。

        Returns:
            是否全部按预期加载成功。注意：图库缺失会返回 False，但已经加载的
            部分仍然可用（对应旧 pipeline 里「只做模板匹配」的场景）。
        """
        if bundle is not None:
            self.bundle = Path(bundle)
        if self.bundle is None:
            raise ValueError("未指定资源包路径")

        root = self.bundle
        ok = True

        image_dir = root / "image"
        if image_dir.is_dir():
            logger.info("加载模板图库：%s", image_dir)
            if not self.resource.post_image(str(image_dir)).wait().succeeded:
                logger.error("模板图库加载失败：%s", image_dir)
                ok = False
        else:
            logger.error("资源包缺少 image/ 目录：%s", image_dir)
            ok = False

        if with_ocr:
            ocr_dir = root / "model" / "ocr"
            if ocr_dir.is_dir():
                logger.info("加载 OCR 模型：%s", ocr_dir)
                if not self.resource.post_ocr_model(str(ocr_dir)).wait().succeeded:
                    logger.error(
                        "OCR 模型加载失败：%s\n"
                        "  请确认目录里有 det.onnx / rec.onnx / keys.txt",
                        ocr_dir,
                    )
                    ok = False
            else:
                logger.error(
                    "资源包缺少 OCR 模型目录：%s\n"
                    "  可从 https://github.com/MaaXYZ/MaaCommonAssets 的 OCR/ppocr_v5/zh_cn "
                    "取 det.onnx / rec.onnx / keys.txt 放进去",
                    ocr_dir,
                )
                ok = False

        if with_pipeline:
            ok = self.load_pipeline(root / "pipeline") and ok

        # 自定义动作/识别挂到 Resource 上。放在资源加载之后：maa 侧注册要求
        # 动作名与识别名互不重名，且需要一个可用的 resource handle。
        if with_custom:
            try:
                actions.discover()
                if len(actions):
                    actions.attach(self.resource)
            except Exception as exc:  # noqa: BLE001 - 自定义扩展坏掉不该让整套资源加载失败
                logger.error("挂载自定义动作/识别失败：%s", exc)

        self._loaded = ok
        return ok

    def load_pipeline(self, path: Union[str, Path]) -> bool:
        """加载一份 pipeline（目录或单个 json）。

        新架构的 Python 任务用不到它；它是给**还没迁移完的旧流水线任务**用的 ——
        这些任务把 ``entry`` 交给 maafw 原生执行，所以节点表必须在。
        """
        target = Path(path)
        if not target.exists():
            logger.error("pipeline 路径不存在：%s", target)
            return False
        logger.info("加载旧流水线：%s", target)
        return bool(self.resource.post_pipeline(str(target)).wait().succeeded)

    # ------------------------------------------------------------------ 状态

    @property
    def loaded(self) -> bool:
        return self._loaded and bool(self.resource.loaded)

    def override_pipeline(self, data: dict) -> bool:
        return bool(self.resource.override_pipeline(data))

    def clear(self) -> None:
        self.resource.clear()
        self._loaded = False
