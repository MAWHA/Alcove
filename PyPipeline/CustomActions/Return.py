from maa.custom_action import CustomAction
from maa.context import Context
from MWATools.MWALogging import logger
import time

class Return(CustomAction):
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        while True:
            return_plot_detail = context.run_recognition("skip_return_Plot",
                                    image=context.tasker.controller.post_screencap().wait().get(),
                                    pipeline_override={"skip_return_Plot":{"recognition": "OCR",
                                                                            "expected": "没人"}})
            if return_plot_detail:
                context.run_task("skip_return_Plot", pipeline_override={"skip_return_Plot":{"recognition": "TemplateMatch",
                                                                                            "template": "return/skip_plot.png",
                                                                                            "action":"Click"}})
                logger.info("跳过回归剧情")

            Claim_return_rewards = context.run_task("Claim_return_rewards",
                                                    pipeline_override={"Claim_return_rewards":{"recognition": "OCR",
                                                                                        "expected": "领取",
                                                                                            "action":"Click"}})
            if Claim_return_rewards:
                time.sleep(1)
                context.tasker.controller.post_click(400,200)
                logger.info("领取回归奖励")
                return True