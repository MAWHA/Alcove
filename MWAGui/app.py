"""Alcove 的 Flet 界面。

三条原则：

1. **后台干活，主线程只画界面。** maafw 的 ``.wait()`` 全是阻塞调用，
   统一丢进 ``page.run_thread``；界面线程只从队列里取消息刷新控件。
2. **界面不猜业务。** 任务列表来自 ``MWATools.MWATask`` 的注册表，
   勾选框和参数控件都是照着 ``TaskSpec`` / ``Option`` 生成的，
   以后加任务模块，界面不用改一行。
3. **事件驱动而不是轮询。** 后台通过 ``Events`` 总线推截图、步骤、日志，
   这里的订阅者只做一件事：塞进队列。
"""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from typing import Any, Optional

import flet as ft

from MWATools import MWAController, MWATask, MWATasker
from MWATools.MWALogging import Events, events, get_logger, install_gui_handler
from MWATools.MWAImage import encode_png, to_data_uri
from MWATools.MWAPaths import LOG_DIR

logger = get_logger("界面")

PREVIEW_WIDTH = 960        # 预览图抽稀宽度：够看清楚，又不至于每帧传几 MB
PUMP_INTERVAL = 0.08       # 队列泵的间隔（秒）
MAX_LOG_LINES = 800

_LEVEL_COLORS = {
    "DEBUG": ft.Colors.ON_SURFACE_VARIANT,
    "INFO": ft.Colors.ON_SURFACE,
    "WARNING": ft.Colors.ORANGE,
    "ERROR": ft.Colors.ERROR,
    "CRITICAL": ft.Colors.ERROR,
}


class AlcoveApp:
    """把 MWATools 的能力接到 Flet 界面上。"""

    def __init__(self, page: ft.Page, *, bundle: Optional[str] = None,
                 debug: bool = False, with_pipeline: bool = True) -> None:
        self.page = page
        self.bundle = bundle
        self.debug = debug
        # 旧流水线任务（还没迁成 Python 的那些）需要 pipeline 节点表。
        self.with_pipeline = with_pipeline

        self.runner: Optional[MWATasker.MWATaskerClass] = None
        self.targets: list = []

        self._busy = False
        self._connecting = False
        self._stop_flag = threading.Event()
        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self._log_lines: list[ft.Text] = []
        self._unsubscribers: list = []

        self._task_checks: dict[str, ft.Checkbox] = {}
        self._option_widgets: dict[tuple[str, str], Any] = {}

        self._build_page()
        self._build_views()
        self._select_view(0)

        page.run_task(self._pump)
        self._unsubscribers.append(events.subscribe(Events.LOG, self._on_log))
        self._unsubscribers.append(events.subscribe(Events.SCREEN, self._on_screen))
        self._unsubscribers.append(events.subscribe(Events.STEP, self._on_step))
        self._unsubscribers.append(events.subscribe(Events.TASK_START, self._on_task_start))
        self._unsubscribers.append(events.subscribe(Events.TASK_END, self._on_task_end))
        self._unsubscribers.append(events.subscribe(Events.FINISHED, self._on_finished))
        page.on_disconnect = self._on_disconnect

        install_gui_handler()
        self.refresh_devices()

    # ============================================================== 页面骨架

    def _build_page(self) -> None:
        page = self.page
        page.title = "Alcove · 物华弥新小助手"
        page.theme_mode = ft.ThemeMode.DARK
        page.theme = ft.Theme(color_scheme_seed="#7aa2f7")
        page.padding = 0
        page.bgcolor = ft.Colors.SURFACE
        page.window.width = 1240
        page.window.height = 800
        page.window.min_width = 1000
        page.window.min_height = 660

    def _build_views(self) -> None:
        self.rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=88,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            indicator_color=ft.Colors.PRIMARY_CONTAINER,
            destinations=[
                ft.NavigationRailDestination(icon=ft.Icons.PLAY_CIRCLE_FILLED, label="运行"),
                ft.NavigationRailDestination(icon=ft.Icons.ARTICLE, label="日志"),
                ft.NavigationRailDestination(icon=ft.Icons.TUNE, label="设置"),
            ],
            on_change=lambda e: self._select_view(int(e.control.selected_index)),
        )

        self.body = ft.Container(expand=True, padding=20)
        self.views = [self._build_run_view(), self._build_log_view(), self._build_settings_view()]

        self.page.add(
            ft.Row(
                controls=[self.rail, ft.VerticalDivider(width=1), self.body],
                expand=True,
                spacing=0,
            )
        )

    def _select_view(self, index: int) -> None:
        self.rail.selected_index = index
        self.body.content = self.views[index]
        self.page.update()

    # -------------------------------------------------------------- 运行页

    def _build_run_view(self) -> ft.Control:
        self.device_dropdown = ft.Dropdown(
            label="控制目标",
            hint_text="先刷新，再选一个设备或窗口",
            options=[],
            expand=True,
            on_select=lambda e: None,
        )
        self.refresh_button = ft.IconButton(
            icon=ft.Icons.REFRESH, tooltip="重新搜索设备", on_click=lambda e: self.refresh_devices()
        )
        self.connect_button = ft.FilledButton(
            content=ft.Text("连接"), icon=ft.Icons.LINK, on_click=self._on_connect
        )
        self.conn_badge = ft.Container(
            content=ft.Text("未连接", size=12),
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=20,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        )

        header = ft.Row(
            controls=[
                self.device_dropdown,
                self.refresh_button,
                self.connect_button,
                self.conn_badge,
            ],
            spacing=10,
        )

        # 实时画面
        self.preview_image = ft.Image(src="", fit=ft.BoxFit.CONTAIN, expand=True)
        self.preview_placeholder = ft.Column(
            controls=[
                ft.Icon(ft.Icons.PHOTO_CAMERA, size=52, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text("还没有画面", color=ft.Colors.ON_SURFACE_VARIANT),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )
        self.preview_box = ft.Container(
            content=self.preview_placeholder,
            expand=True,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=14,
            alignment=ft.Alignment.CENTER,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
        self.step_text = ft.Text("等待开始", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
        self.progress = ft.ProgressBar(value=0, bar_height=4, border_radius=2)

        left = ft.Column(
            controls=[
                self.preview_box,
                self.step_text,
                self.progress,
            ],
            spacing=12,
            expand=3,
        )

        # 任务勾选 + 参数
        self.task_list = ft.ListView(expand=True, spacing=2, padding=0)
        self._fill_task_list()

        right = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE, size=18, color=ft.Colors.PRIMARY),
                        ft.Text("任务", weight=ft.FontWeight.BOLD),
                    ],
                    spacing=6,
                ),
                ft.Container(
                    content=self.task_list,
                    expand=True,
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border_radius=14,
                    padding=10,
                ),
            ],
            spacing=10,
            expand=2,
        )

        self.stop_on_error = ft.Switch(label="任务失败就停下", value=False)
        self.start_button = ft.FilledButton(
            content=ft.Text("开始"), icon=ft.Icons.PLAY_ARROW, on_click=self._on_start
        )
        self.stop_button = ft.OutlinedButton(
            content=ft.Text("停止"), icon=ft.Icons.STOP, on_click=self._on_stop, disabled=True
        )
        self.run_status = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT, expand=True)

        footer = ft.Row(
            controls=[
                self.start_button,
                self.stop_button,
                self.stop_on_error,
                self.run_status,
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Column(
            controls=[
                header,
                ft.Row(controls=[left, right], spacing=16, expand=True),
                footer,
            ],
            spacing=16,
            expand=True,
        )

    def _fill_task_list(self) -> None:
        """照着任务注册表把勾选框和参数控件画出来。"""
        self.task_list.controls.clear()
        self._task_checks.clear()
        self._option_widgets.clear()

        specs = MWATask.all_tasks()
        if not specs:
            self.task_list.controls.append(
                ft.Text("没有加载到任何任务模块", color=ft.Colors.ERROR)
            )
            return

        groups: dict[str, list[MWATask.TaskSpec]] = {}
        for spec in specs:
            groups.setdefault(spec.group, []).append(spec)

        for group, group_specs in groups.items():
            self.task_list.controls.append(
                ft.Container(
                    content=ft.Text(group, size=11, weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.PRIMARY),
                    padding=ft.Padding.only(top=8, bottom=2, left=2),
                )
            )
            for spec in group_specs:
                checkbox = ft.Checkbox(
                    label=spec.key,
                    value=spec.default_enabled,
                    tooltip=spec.description or None,
                )
                self._task_checks[spec.key] = checkbox
                self.task_list.controls.append(checkbox)

                for option in spec.options:
                    widget = self._option_widget(spec, option)
                    self._option_widgets[(spec.key, option.key)] = widget
                    self.task_list.controls.append(
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Text(option.label or option.key, size=12,
                                            color=ft.Colors.ON_SURFACE_VARIANT),
                                    widget,
                                ],
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            padding=ft.Padding.only(left=32, bottom=2),
                        )
                    )

    def _option_widget(self, spec: MWATask.TaskSpec, option: MWATask.Option) -> ft.Control:
        """按选项声明类型给一个合适的控件。"""
        choices = [choice.value for choice in option.choices]

        if option.kind in ("switch", "bool"):
            return ft.Switch(value=bool(option.default))
        if option.kind in ("checkbox",):
            return ft.Switch(value=bool(option.default))
        if option.kind == "int" and choices:
            return ft.Dropdown(
                value=option.default if option.default in choices else choices[0],
                options=[ft.DropdownOption(key=str(c), text=str(c)) for c in choices],
                width=160,
            )
        if option.kind in ("int", "str"):
            return ft.TextField(
                value="" if option.default is None else str(option.default), width=120
            )
        # select（默认）
        return ft.Dropdown(
            value=option.default if option.default in choices else (choices[0] if choices else None),
            options=[ft.DropdownOption(key=str(c), text=str(c)) for c in choices],
            width=220,
        )

    def _collect_settings(self, keys: list[str]) -> dict[str, dict[str, Any]]:
        settings: dict[str, dict[str, Any]] = {}
        for key in keys:
            spec = MWATask.get_task(key)
            if spec is None or not spec.options:
                continue
            values: dict[str, Any] = {}
            for option in spec.options:
                widget = self._option_widgets.get((key, option.key))
                if widget is None:
                    continue
                value = getattr(widget, "value", None)
                if isinstance(widget, ft.TextField) and option.kind == "int":
                    try:
                        value = int(str(value).strip() or option.default or 0)
                    except ValueError:
                        value = option.default
                values[option.key] = value
            settings[key] = values
        return settings

    # -------------------------------------------------------------- 日志页

    def _build_log_view(self) -> ft.Control:
        self.log_list = ft.ListView(
            expand=True, spacing=2, padding=10, auto_scroll=True
        )
        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ARTICLE, size=18, color=ft.Colors.PRIMARY),
                        ft.Text("运行日志", weight=ft.FontWeight.BOLD),
                        ft.Text(f"· 文件在 {LOG_DIR}", size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                    spacing=6,
                ),
                ft.Container(
                    content=self.log_list,
                    expand=True,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    border_radius=14,
                ),
            ],
            spacing=10,
            expand=True,
        )

    def _append_log(self, level: str, text: str) -> None:
        control = ft.Text(
            value=text, size=12, selectable=True,
            font_family="monospace",
            color=_LEVEL_COLORS.get(level, ft.Colors.ON_SURFACE),
        )
        self._log_lines.append(control)
        self.log_list.controls.append(control)
        del self._log_lines[:-MAX_LOG_LINES]
        if len(self.log_list.controls) > MAX_LOG_LINES:
            del self.log_list.controls[:-MAX_LOG_LINES]

    # -------------------------------------------------------------- 设置页

    def _build_settings_view(self) -> ft.Control:
        self.bundle_field = ft.TextField(
            label="资源包目录", value=self.bundle or MWATasker.DEFAULT_BUNDLE,
            expand=True, read_only=True,
        )
        self.theme_switch = ft.Switch(
            label="深色主题", value=True,
            on_change=self._on_theme_change,
        )
        self.debug_switch = ft.Switch(label="调试模式（maafw 存图 + 详细日志）", value=self.debug)

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.TUNE, size=18, color=ft.Colors.PRIMARY),
                        ft.Text("设置", weight=ft.FontWeight.BOLD),
                    ],
                    spacing=6,
                ),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            self.bundle_field,
                            self.theme_switch,
                            self.debug_switch,
                            ft.Divider(),
                            ft.Text("说明", weight=ft.FontWeight.BOLD, size=13),
                            ft.Text(
                                "任务列表来自 PyPipeline/Tasks/ 下各模块的 @task 声明；\n"
                                "新增一个任务模块，界面会自动出现对应的勾选框。",
                                size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=14,
                    ),
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border_radius=14,
                    padding=18,
                ),
            ],
            spacing=10,
        )

    def _on_theme_change(self, e) -> None:
        self.page.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        self.page.update()

    # ============================================================== 设备

    def refresh_devices(self) -> None:
        try:
            self.targets = MWAController.list_targets()
        except Exception as exc:
            logger.error("搜索设备失败：%s", exc)
            self.targets = []

        self.device_dropdown.options = [
            ft.DropdownOption(key=str(index), text=target.label)
            for index, target in enumerate(self.targets)
        ]
        if self.targets and self.device_dropdown.value is None:
            self.device_dropdown.value = "0"
        self.device_dropdown.hint_text = (
            "先刷新，再选一个设备或窗口" if self.targets else "没有找到设备"
        )
        self.page.update()

    def _on_connect(self, e) -> None:
        if self._connecting:
            return
        if self.runner is not None:
            self._disconnect()
            return

        raw = self.device_dropdown.value
        if raw is None or not self.targets:
            self._set_conn("没有可用设备", ok=False)
            return
        try:
            target = self.targets[int(raw)]
        except (ValueError, IndexError):
            self._set_conn("设备选择无效", ok=False)
            return

        self._connecting = True
        self.connect_button.disabled = True
        self._set_conn("连接中…")
        self.page.run_thread(lambda: self._connect_worker(target))

    def _connect_worker(self, target) -> None:
        runner = MWATasker.MWATaskerClass()
        try:
            ok = runner.start(
                target,
                self.bundle,
                with_ocr=True,
                with_pipeline=self.with_pipeline,
                debug=bool(getattr(self, "debug_switch", None) and self.debug_switch.value),
            )
        except Exception as exc:
            logger.error("连接时异常：%s", exc, exc_info=True)
            ok = False
        self._queue.put(("connected", runner if ok else None, target.label))

    def _disconnect(self) -> None:
        try:
            self.runner.stop()
        except Exception:
            pass
        self.runner = None
        self._set_conn("未连接")
        if self.connect_button.content is not None:
            self.connect_button.content = ft.Text("连接")
        self.connect_button.icon = ft.Icons.LINK
        self.page.update()

    def _set_conn(self, text: str, *, ok: Optional[bool] = None) -> None:
        color = ft.Colors.SURFACE_CONTAINER_HIGHEST
        if ok is True:
            color = ft.Colors.PRIMARY_CONTAINER
        elif ok is False:
            color = ft.Colors.ERROR_CONTAINER
        self.conn_badge.bgcolor = color
        self.conn_badge.content = ft.Text(text, size=12)
        self.page.update()

    def _on_disconnect(self, e) -> None:
        """窗口关掉时别把后台线程留着。"""
        self._stop_flag.set()
        for unsubscribe in self._unsubscribers:
            try:
                unsubscribe()
            except Exception:
                pass

    # ============================================================== 运行

    def _on_start(self, e) -> None:
        if self._busy:
            return
        if self.runner is None:
            self._set_run_status("还没连接设备", error=True)
            return

        keys = [key for key, box in self._task_checks.items() if box.value]
        if not keys:
            self._set_run_status("没有勾选任何任务", error=True)
            return

        settings = self._collect_settings(keys)
        self._stop_flag.clear()
        self._busy = True
        self.start_button.disabled = True
        self.stop_button.disabled = False
        self.progress.value = 0
        self._set_run_status(f"开始运行 {len(keys)} 个任务")
        self.page.update()

        self.page.run_thread(lambda: self._run_worker(keys, settings))

    def _run_worker(self, keys: list[str], settings: dict) -> None:
        try:
            runner = MWATask.TaskRunner(self.runner.screen, cancel=self._stop_flag.is_set)
            runner.run(
                keys,
                settings=settings,
                stop_on_error=bool(self.stop_on_error.value),
            )
        except Exception as exc:
            logger.error("运行任务时异常：%s", exc, exc_info=True)
            self._queue.put(("run_error", str(exc)))
        finally:
            self._busy = False
            self._queue.put(("run_done", None))

    def _on_stop(self, e) -> None:
        self._stop_flag.set()
        self._set_run_status("正在停止…")
        if self.runner is not None:
            try:
                self.runner.tasker.post_stop()
            except Exception:
                pass

    def _set_run_status(self, text: str, *, error: bool = False) -> None:
        self.run_status.value = text
        self.run_status.color = ft.Colors.ERROR if error else ft.Colors.ON_SURFACE_VARIANT

    # ============================================================== 事件订阅
    # 订阅者跑在后台线程上，只往队列里塞东西，绝不碰控件。

    def _on_log(self, level: str, text: str) -> None:
        self._queue.put(("log", level, text))

    def _on_screen(self, image) -> None:
        if self._busy or self.runner is not None:
            try:
                uri = to_data_uri(encode_png(image, max_width=PREVIEW_WIDTH))
            except Exception:
                return
            self._queue.put(("screen", uri))

    def _on_step(self, text: str) -> None:
        self._queue.put(("step", text))

    def _on_task_start(self, key: str, label: str) -> None:
        self._queue.put(("task", key, label, True))

    def _on_task_end(self, key: str, success: bool, elapsed: float) -> None:
        self._queue.put(("task", key, "", success))

    def _on_finished(self, results: list) -> None:
        self._queue.put(("results", results))

    # ============================================================== 队列泵

    async def _pump(self) -> None:
        """把后台消息搬到控件上。整条链路只有这里改界面。"""
        while True:
            dirty = False
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline:
                try:
                    message = self._queue.get_nowait()
                except queue.Empty:
                    break
                dirty |= self._apply(message)

            if dirty:
                try:
                    self.page.update()
                except Exception:
                    pass
            await asyncio.sleep(PUMP_INTERVAL)

    def _apply(self, message: tuple) -> bool:
        kind = message[0]

        if kind == "log":
            self._append_log(message[1], message[2])
            return True

        if kind == "screen":
            if self.preview_box.content is not self.preview_image:
                self.preview_box.content = self.preview_image
            self.preview_image.src = message[1]
            return True

        if kind == "step":
            self.step_text.value = message[1]
            return True

        if kind == "task":
            _, key, label, started = message
            if started:
                self._set_run_status(f"正在运行：{label}")
                self.step_text.value = f"{label} …"
            return True

        if kind == "results":
            self.progress.value = 1
            done = len(message[1])
            ok = sum(1 for item in message[1] if item.get("success"))
            failed = [item["name"] for item in message[1]
                      if not item.get("success") and not item.get("cancelled")]
            if failed:
                self._set_run_status(f"完成 {done} 个，{ok} 成功；失败：{'、'.join(failed)}",
                                     error=True)
            else:
                self._set_run_status(f"全部完成（{done} 个任务，{ok} 成功）")
            return True

        if kind == "run_error":
            self._set_run_status(f"运行出错：{message[1]}", error=True)
            return True

        if kind == "run_done":
            self._busy = False
            self.start_button.disabled = False
            self.stop_button.disabled = True
            self.step_text.value = "已结束"
            return True

        if kind == "connected":
            self._connecting = False
            self.connect_button.disabled = False
            self.runner = message[1]
            if self.runner is None:
                self._set_conn("连接失败", ok=False)
            else:
                self.connect_button.content = ft.Text("断开")
                self.connect_button.icon = ft.Icons.LINK_OFF
                self._set_conn(f"已连接 {message[2]}", ok=True)
            return True

        return False


def run(bundle: Optional[str] = None, device: Optional[str] = None,
        debug: bool = False, with_pipeline: bool = True) -> int:
    """启动图形界面（阻塞直到窗口关闭）。"""

    def main(page: ft.Page) -> None:
        AlcoveApp(page, bundle=bundle, debug=debug, with_pipeline=with_pipeline)

    # 注意：flet 1.0 的公开入口是 ft.run，不是 0.2x 时代的 ft.app(target=...)。
    # ft.app 只是子模块名，且要等别处 import 过 flet.app 之后才能当属性访问，
    # 直接写 ft.app(...) 在某些导入顺序下会 AttributeError。
    ft.run(main, name="Alcove")
    return 0
