"""option → ``pipeline_override`` 合并器（等价于 MaaPiCli 的 Configurator）。

**这是把 interface.json 真正跑起来的那一步。**

``Tasker.post_task(entry, pipeline_override)`` 的第二个参数除了单个 dict，
还接受**有序的对象数组**：MaaFramework 原生会按数组顺序逐个把它当成
「以当前累积结果为默认值的部分节点」解析，于是得到**节点内字段级浅合并、
后者覆盖前者**，而 ``next`` / ``on_error`` 这类列表字段是整体替换。
官方 C++ runner（MaaPiCli）就是这么干的：把 ``task.pipeline_override`` 和
各个命中 case 的 override **按顺序 append 成数组**，交给原生去做合并。

因此本模块**不需要**自己实现深合并 —— 只需要按官方顺序把 override 收集起来：

1. 任务自己的 ``pipeline_override``（如果有）—— 作为基准，最先
2. ``global_option`` 里被选中的项
3. 当前 ``resource`` 的 ``option``
4. 当前 ``controller`` 的 ``option``
5. ``task.option`` 里被选中的项（**优先级最高，最后合并，所以它说了算**）

每一步里再按 option 定义的顺序逐个合并；checkbox 类型的多个命中 case，
按 ``cases`` 的**数组定义顺序**合并（与用户勾选先后无关）。

适用范围过滤（ProjectInterface v2）：option 可以声明 ``controller`` /
``resource`` 限定，当前选择不在其中时该 option（及其子 option）整体不产生
override。

关于「没选过的 option」：官方 runner 遇到空值会 warn 后跳过。这里默认
``use_defaults=True``，会退回 ``default_case``（没有则第一个 case），
因为 CLI / GUI 都是「默认勾上第一项」的交互，这样行为与旧 GUI 一致。
要严格复刻官方行为就把 ``use_defaults`` 设成 False。
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Optional

from .MWALogging import get_logger
from .MWAReadTask import MWAReadTaskClass

__all__ = ["MWATaskPipelineClass", "DEFAULT_MERGE_ORDER"]

logger = get_logger("流水线合并")

#: 官方合并顺序：越靠后优先级越高。
DEFAULT_MERGE_ORDER = ("global_option", "resource", "controller", "task")


class MWATaskPipelineClass(MWAReadTaskClass):
    """读 interface.json + 记下用户选择 + 产出可直接喂给 ``post_task`` 的 override。"""

    def __init__(self, path=None, *, interface=None, use_defaults: bool = True) -> None:
        super().__init__(path, interface=interface)

        #: 旧字段名保留。旧版是「一坨 entry/option 混在一起的 list」，
        #: 现在每个元素是一条完整的任务计划（有 entry、有选项），含义更明确。
        self.pipelines: list[dict[str, Any]] = []

        #: option 键 -> 取值。select/switch 是 case 名（str）；
        #: checkbox 是 case 名列表（list[str]）；input 是 {字段: 值}（dict）。
        self.selection: dict[str, Any] = {}

        self.controller: Optional[str] = None
        self.resource: Optional[str] = None
        self.use_defaults = use_defaults

        self._warned: set[str] = set()

    # ================================================================== 旧接口

    def add_pipeline(self, task_name: str, options: bool = False) -> list[dict[str, Any]]:
        """把一条任务加进 ``self.pipelines``。

        旧签名 ``add_pipeline(task_name, options=False)`` 保持不变；``options=True``
        时额外把该任务引用到的 option 键名列表记进去（旧版塞的是原始 list，
        现在塞进结构化字段里，用起来更省事）。
        """
        entry = self.get_task_entry(task_name)
        if entry is None:
            logger.warning("任务 %r 不在 interface.json 里，已跳过", task_name)
            return self.pipelines

        plan: dict[str, Any] = {"name": task_name, "entry": entry}
        if options:
            plan["options"] = self.task_options(task_name)
        self.pipelines.append(plan)
        return self.pipelines

    def clear_pipelines(self) -> None:
        self.pipelines.clear()

    # ================================================================== 选择

    def set_option(self, option_key: str, value: Any) -> "MWATaskPipelineClass":
        """选定一个 option 的取值。未知 option 只记 debug，不抛异常。"""
        if option_key not in self.options:
            logger.debug("未知 option %r，已记下但不会产生 override", option_key)
        self.selection[option_key] = value
        return self

    def set_options(self, mapping: Optional[dict[str, Any]]) -> "MWATaskPipelineClass":
        for key, value in (mapping or {}).items():
            self.set_option(key, value)
        return self

    def clear_selection(self) -> "MWATaskPipelineClass":
        self.selection.clear()
        return self

    def select_case(self, option_key: str, case_name: str) -> "MWATaskPipelineClass":
        return self.set_option(option_key, case_name)

    def select_case_by_label(self, option_key: str, label: str) -> "MWATaskPipelineClass":
        """按显示名选 —— CLI / GUI 上看到的通常是 label。"""
        case = self.case_by_label(option_key, label)
        return self.set_option(option_key, case.get("name") if case else label)

    def effective_value(self, option_key: str) -> Any:
        """取某个 option 的最终取值（用户没选时按 ``use_defaults`` 兜底）。"""
        if option_key in self.selection:
            return self.selection[option_key]
        if not self.use_defaults:
            return None

        kind = self.option_type(option_key)
        if kind == "checkbox":
            names = self.case_names(option_key)
            return names
        if kind == "input":
            return {
                str(item.get("name", "")): item.get("default")
                for item in (self.get_option(option_key) or {}).get("inputs", [])
                if isinstance(item, dict)
            }
        return self.default_case(option_key)

    def selection_for(self, task_name: str) -> dict[str, Any]:
        """只保留该任务（含其 option 的嵌套 option）真正会用到的选择。"""
        keys: list[str] = []
        for key in self._option_chain(task_name):
            if key not in keys:
                keys.append(key)
        return {k: self.effective_value(k) for k in keys}

    def missing_options(self, task_name: str) -> list[str]:
        """该任务用到、但既没选过、也没法兜底（无 cases / 无 inputs）的 option。"""
        missing: list[str] = []
        for option_key in self._option_chain(task_name):
            if option_key in self.selection:
                continue
            value = self.effective_value(option_key)
            if value in (None, "", [], {}):
                missing.append(option_key)
        return missing

    # ================================================================== 合并

    def _option_chain(self, task_name: str) -> list[str]:
        """按官方优先级顺序列出该任务会用到的 option 键名（低 → 高）。"""
        task = self.get_task(task_name) or {}
        chain: list[str] = []

        def extend(keys: Any) -> None:
            if isinstance(keys, list):
                for key in keys:
                    if isinstance(key, str) and key not in chain:
                        chain.append(key)

        # 1. 全局
        extend(self.data.get("global_option"))
        # 2. 资源包自己的 option（interface.json 里 resource[].option）
        for entry in self.interface.resources():
            if self.resource is None or entry.get("name") == self.resource:
                extend(entry.get("option"))
        # 3. 控制器自己的 option
        for entry in self.interface.controllers():
            if self.controller is None or entry.get("name") == self.controller:
                extend(entry.get("option"))
        # 4. 任务自己的 option —— 优先级最高
        extend(task.get("option"))
        return chain

    def _merge_case(self, option_key: str, case: dict[str, Any], out: list[dict[str, Any]]) -> None:
        override = case.get("pipeline_override")
        if isinstance(override, dict) and override:
            out.append(override)
        # case 自己还可以带子 option（无限嵌套）
        sub_keys = case.get("option")
        if isinstance(sub_keys, list):
            for sub_key in sub_keys:
                if isinstance(sub_key, str):
                    self._merge_option(sub_key, out, seen=set())

    def _substitute(self, template: Any, values: dict[str, Any], option_key: str) -> Any:
        """按 ProjectInterface v2 的规则做 ``{字段名}`` 占位符替换。

        字符串型：先替换带引号的 ``"{字段}"``，再替换裸的 ``{字段}``；
        数字/布尔型：两种情况都换成**裸值**（不要引号，否则进了 JSON 就是字符串）。
        """
        if not isinstance(values, dict):
            return template

        raw = json.dumps(template, ensure_ascii=False)
        for field_name, value in values.items():
            inputs = {
                str(item.get("name", "")): item
                for item in (self.get_option(option_key) or {}).get("inputs", [])
                if isinstance(item, dict)
            }
            field_type = str((inputs.get(field_name) or {}).get("pipeline_type") or "string").lower()

            if field_type in ("int", "integer", "bool", "boolean"):
                text = "true" if value is True else ("false" if value is False else str(value))
            else:
                text = json.dumps("" if value is None else str(value), ensure_ascii=False)

            raw = raw.replace('"{' + field_name + '}"', text)
            raw = raw.replace("{" + field_name + "}", text)

        try:
            return json.loads(raw)
        except ValueError as exc:
            logger.error("option %r 的 input 模板替换后不是合法 JSON：%s", option_key, exc)
            return template

    def _merge_option(self, option_key: str, out: list[dict[str, Any]], *, seen: set[str]) -> None:
        if option_key in seen:
            return
        seen.add(option_key)

        option = self.get_option(option_key)
        if option is None:
            self._warn_once(option_key, "option %r 不在 interface.json 的 option 表里，已忽略")
            return

        if not self.is_option_applicable(option_key, self.controller, self.resource):
            logger.debug("option %r 不适用于当前 controller/resource，已跳过", option_key)
            return

        value = self.effective_value(option_key)
        kind = self.option_type(option_key)

        if kind == "checkbox":
            selected = value if isinstance(value, (list, tuple, set)) else ([value] if value else [])
            selected = {str(v) for v in selected}
            if not selected:
                return
            # 按 cases 的定义顺序合并，与勾选先后无关
            for case in self.get_cases(option_key):
                if str(case.get("name", "")) in selected:
                    self._merge_case(option_key, case, out)
            return

        if kind == "input":
            template = option.get("pipeline_override")
            if isinstance(template, dict) and template:
                merged = self._substitute(template, value if isinstance(value, dict) else {}, option_key)
                if isinstance(merged, dict) and merged:
                    out.append(merged)
            return

        # select / switch / hotkey：按 case.name 精确匹配
        if value in (None, ""):
            self._warn_once(option_key, "option %r 没有取值，已跳过")
            return
        case = self.case(option_key, str(value))
        if case is None:
            self._warn_once(
                option_key,
                f"option %r 的取值不是任何 case.name（可选：{self.case_names(option_key)}），已跳过",
            )
            return
        self._merge_case(option_key, case, out)

    def _warn_once(self, key: str, message: str) -> None:
        if key in self._warned:
            return
        self._warned.add(key)
        logger.warning(message, key)

    def build_override(self, task_name: str) -> list[dict[str, Any]]:
        """产出该任务最终的有序 override 列表（可直接传给 ``post_task``）。"""
        out: list[dict[str, Any]] = []

        task = self.get_task(task_name)
        if task is None:
            logger.warning("任务 %r 不在 interface.json 里，产不出 override", task_name)
            return out

        base = task.get("pipeline_override")
        if isinstance(base, dict) and base:
            out.append(base)

        for option_key in self._option_chain(task_name):
            self._merge_option(option_key, out, seen=set())

        return out

    def build(self, task_name: str) -> dict[str, Any]:
        """产出一条完整的执行计划：``{'name', 'entry', 'pipeline_override', 'missing'}``。"""
        missing = self.missing_options(task_name)
        if missing:
            logger.warning("任务 %r 有 %d 个选项没有取值：%s", task_name, len(missing), missing)
        return {
            "name": task_name,
            "entry": self.get_task_entry(task_name),
            "pipeline_override": self.build_override(task_name),
            "missing": missing,
        }

    def build_all(self) -> list[dict[str, Any]]:
        """把 :meth:`add_pipeline` 收集进来的任务全部产出计划。"""
        names = [str(p.get("name")) for p in self.pipelines] or list(self.tasks)
        return [self.build(name) for name in names]

    def plan(self, task_names: Iterable[str], selection: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        """一步到位：给定任务名与选择，产出全部执行计划。"""
        if selection:
            self.set_options(selection)
        self.clear_pipelines()
        for name in task_names:
            self.add_pipeline(name)
        return self.build_all()

    # ================================================================== 展示

    def describe_selection(self, task_name: Optional[str] = None) -> str:
        keys = self._option_chain(task_name) if task_name else list(self.options)
        lines: list[str] = []
        for key in keys:
            value = self.effective_value(key)
            if value is None:
                continue
            lines.append(f"  {key} = {value!r}")
        return "\n".join(lines) or "  （没有选中任何选项）"


if __name__ == "__main__":
    from .MWALogging import setup_logging

    setup_logging()
    pipe = MWATaskPipelineClass()
    pipe.set_options(
        {
            "领取资源、好感、售卖机": "领取奖励",
            "是否喝茶": "喝茶",
            "选择战斗次数": "打一次（速通解锁专用）",
        }
    )
    for name in ("启动", "派遣公司", "资源", "良宵百载"):
        plan = pipe.build(name)
        print(f"\n【{name}】entry={plan['entry']}  override {len(plan['pipeline_override'])} 段")
        for index, chunk in enumerate(plan["pipeline_override"]):
            print(f"   [{index}] {json.dumps(chunk, ensure_ascii=False)}")
        if plan["missing"]:
            print(f"   缺选项: {plan['missing']}")
