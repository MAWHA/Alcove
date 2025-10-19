from maa.custom_action import CustomAction
from maa.context import Context
from MWATools.MWALogging import logger
import time


class StartApp(CustomAction):
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        context.tasker.controller.post_start_app("com.cipaishe.wuhua.bilibili")
        while True:
            
            RecoUpdate = context.run_recognition("RecoUpdate",
                                                image=context.tasker.controller.post_screencap().wait().get(),
                                                pipeline_override={"RecoUpdate":{"recognition": "OCR",
                                                                                 "expected": "检测到终端数据更新"}})
            if RecoUpdate != None:
                time.sleep(1)
                context.tasker.controller.post_click(765, 430)
                logger.info("正在更新物华弥新...")

            RecoAnnouncement = context.run_recognition("RecoAnnouncement",
                                                image=context.tasker.controller.post_screencap().wait().get(),
                                                pipeline_override={"RecoAnnouncement":{"recognition": "OCR",
                                                                                 "expected": "活动公告"}})
            if RecoAnnouncement != None:
                time.sleep(1)
                CloseAnnouncement = context.run_task("RecoAnnouncement",
                                                pipeline_override={"RecoAnnouncement":{"recognition": "TemplateMatch",
                                                                                 "template": "Startup/12.png",
                                                                                 "action": "Click"}})
                
                logger.info("关闭公告")
            
            EntryGame = context.run_recognition("EntryGame",
                                                image=context.tasker.controller.post_screencap().wait().get(),
                                                pipeline_override={"EntryGame":{"recognition": "OCR",
                                                                                 "expected": "壬音"}})
            if EntryGame != None:
                context.tasker.controller.post_click(EntryGame.best_result.box[0],EntryGame.best_result.box[1])
                time.sleep(5)
                return_plot_detail = context.run_recognition("skip_return_Plot",
                        image=context.tasker.controller.post_screencap().wait().get(),
                        pipeline_override={"skip_return_Plot":{"recognition": "OCR",
                                                                "expected": "没人"}})
                if return_plot_detail:
                    context.run_task("Return", pipeline_override={
                        "Return": {"action": "custom", "custom_action": "Return"},
                    })
                logger.info("进入游戏")
                return True
            
            SignIn = context.run_recognition("SignIn",
                                                image=context.tasker.controller.post_screencap().wait().get(),
                                                pipeline_override={"SignIn":{"recognition": "OCR",
                                                                                 "expected": "请输入手机号"}})

            if SignIn !=None:
                logger.error("登录失败，请用户自行登录")
                return True
            
