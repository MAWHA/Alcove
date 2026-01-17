from maa.custom_action import CustomAction
from maa.context import Context
from MWATools.MWALogging import logger
import time

class OpenRecruitment(CustomAction):
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        logger.info("器者征集任务开始")
        layer = 0
        while True:
            if layer == 0:
                open_recruitment_detail = context.run_recognition("skip_return_Plot",
                                image=context.tasker.controller.post_screencap().wait().get(),
                                pipeline_override={"skip_return_Plot":{"recognition": "OCR",
                                                                        "expected": "器者征集"}})
                if open_recruitment_detail:
                    clicked_recruitment = context.run_task("open_recruitment", pipeline_override={"open_recruitment":{"recognition": "OCR",
                                                                                                "expected": "器者征集",
                                                                                                "action":"Click"}})
                    print(clicked_recruitment.status)
                    if clicked_recruitment.status.succeeded is True:
                        layer = 1
                    logger.info("点击器者征集按钮")

