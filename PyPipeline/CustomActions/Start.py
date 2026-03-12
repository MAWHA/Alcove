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
        RecoUpdate = context.run_recognition("RecoUpdate",
                                            image=context.tasker.controller.post_screencap().wait().get(),
                                            pipeline_override={"RecoUpdate":{"recognition": "OCR",
                                                                                "expected": "检测到终端数据更新",}})
        if RecoUpdate.best_result != "检测到终端数据更新":
            time.sleep(1)
            context.tasker.controller.post_click(765, 430)
            logger.info("正在更新物华弥新...")
        print(1)
        # 等待游戏加载
        while True:
            RecoAnnouncement = context.run_recognition("RecoAnnouncement",
                                    image=context.tasker.controller.post_screencap().wait().get(),
                                    pipeline_override={"RecoAnnouncement":{"roi": [327,83,145,49],
                                                                            "recognition": "OCR",
                                                                            "expected": "活动公告"}})
            # RecoAnnouncement = context.run_recognition_direct(reco_type=OCR,reco_param=[],image=context.tasker.controller.post_screencap().wait().get())
            if  RecoAnnouncement.best_result is not None:
                print("reco announcement:",RecoAnnouncement)
                if RecoAnnouncement.best_result.text == "活动公告":
                    if self._IsInEntryGamePage(context, argv):
                        print("-----------------",self._IsInEntryGamePage(context, argv).best_result)
                        if self._IsInEntryGamePage(context, argv).best_result is not None:
                            logger.info("已经在游戏入口页面")
                            break

                CloseAnnouncement = context.run_task("RecoAnnouncement",
                                    pipeline_override={"RecoAnnouncement":{"roi": [1098,31,154,138],
                                                                        "recognition": "TemplateMatch",
                                                                            "template": "Startup/12.png",
                                                                            "action": "Click"}})
                print("close announcement status:",CloseAnnouncement.status.succeeded)
                logger.info("关闭公告")
                break
            else:
                time.sleep(0.2)
        isinentrygamepage = self._IsInEntryGamePage(context, argv)
        if isinentrygamepage.best_result.text == "抵制不良游戏":
            time.sleep(0.5)
            context.run_task("EntryGame", pipeline_override={"EntryGame":{"target": [303,112,775,453],
                                                                    "action": "Click"}})
            logger.info("进入游戏")
    def _IsInEntryGamePage(self, context: Context, argv: CustomAction.RunArg,):
        IsInEntryGamePage = context.run_recognition("IsInEntryGamePage",
                                image=context.tasker.controller.post_screencap().wait().get(),
                                pipeline_override={"IsInEntryGamePage":{"roi": [223,633,212,34],
                                                                        "recognition": "OCR",
                                                                        "expected": "抵制不良游戏"}})
        return IsInEntryGamePage