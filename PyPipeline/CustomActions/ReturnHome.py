from maa.custom_action import CustomAction
from maa.context import Context
from MWATools.MWALogging import logger
import time

class ReturnHome(CustomAction):
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        logger.info("正在返回主界面")
        if isinhome := context.run_recognition("is_in_home",
                                image=context.tasker.controller.post_screencap().wait().get(),
                                pipeline_override={"is_in_home":{"roi": [884,525,219,89],
                                                                "recognition": "OCR",
                                                                "expected": "器者征集"}}).hit:
            print("+++++",isinhome)
            logger.info("当前已经在主界面")
            return True    
        else:
            if isinhome := context.run_task("is_in_home",
                                pipeline_override={"is_in_home":{"roi": [202,2,79,78],
                                                                "recognition": "TemplateMatch",
                                                                "template": "Startup/10.png",
                                                                "action": "Click"}}).status.succeeded:
                logger.info("返回主界面成功")
                return True
            else:
                if isinhome := context.run_task("is_in_home",
                                pipeline_override={"is_in_home":{"target": [35,13,39,36],
                                                                "recognition": "TemplateMatch",
                                                                "template": "collect/06.png",
                                                                "roi": [17,6,131,49],
                                                                "action": "Click"}}).status.succeeded:
                    if isinhome := context.run_task("is_in_home",
                                pipeline_override={"is_in_home":{"roi": [202,2,79,78],
                                                                "recognition": "TemplateMatch",
                                                                "template": "Startup/10.png",
                                                                "action": "Click"}}).status.succeeded:
                        logger.info("返回主界面成功")
                        return True
                else:
                    self.run(context=context, argv=argv)