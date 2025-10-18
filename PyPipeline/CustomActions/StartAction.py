from maa.custom_action import CustomAction
from maa.context import Context
import time
from maa.event_sink import EventSink


class StartApp(CustomAction):
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        """
        :param argv:
        :param context: 运行上下文
        :return: 是否执行成功。-参考流水线协议 `on_error`
        """
        context.tasker.controller.post_start_app("com.cipaishe.wuhua.bilibili")
        # time.sleep(20)
        # print(context.tasker.controller.post_screencap())
        context.tasker.controller.post_screencap().wait().get()
        # taskdetail = context.run_action("Start",pipeline_override={"Start":{"action": "StartApp","package": "com.cipaishe.wuhua.bilibili"}})
        RecoUpdate = context.run_recognition("RecoUpdate",
                                   image=context.tasker.controller.post_screencap().wait().get(),
                                   pipeline_override={"RecoUpdate":{"recognition": "OCR","expected": "前往更新"}}).best_result.box
        context.tasker.controller.post_click(RecoUpdate.x,RecoUpdate.y)
        # print(context.run_recognition("RecoUpdate",image=context.tasker.controller.post_screencap().wait().get(),pipeline_override={"RecoUpdate":{"recognition": "OCR","expected": "前往更新"}}))

        return True