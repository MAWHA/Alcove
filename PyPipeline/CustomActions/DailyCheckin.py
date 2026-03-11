from maa.custom_action import CustomAction
from maa.context import Context
from MWATools.MWALogging import logger
import time


class DailyCheckin(CustomAction):
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        detail = context.run_recognition("dian",
                                image=context.tasker.controller.post_screencap().wait().get(),
                                pipeline_override={"dian":{"recognition": "OCR",
                                                                    "expected": "点",
                                                                    "roi":[978,106,240,502],
                                                                    "next":"ji"},
                                                    "ji":{"recognition": "OCR",
                                                                    "expected": "击",
                                                                    "roi":[978,106,240,502]}})
        receive = context.tasker.controller.post_click(detail.best_result.box[0],
                                                        detail.best_result.box[1])
        
        detail =  context.run_recognition("dian",
                                image=context.tasker.controller.post_screencap().wait().get(),
                                pipeline_override={"dian":{"recognition": "Temp",
                                                                    "expected": "点",
                                                                    "roi":[978,106,240,502],
                                                                    "next":"ji"}})
        print(detail)
        print("receive:",receive)