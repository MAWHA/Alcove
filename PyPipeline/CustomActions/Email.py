from maa.custom_action import CustomAction
from maa.context import Context
from MWATools.MWALogging import logger
import time

class RecoEmail(CustomAction):
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        
        while True:

            RecoEmail = context.run_recognition("RecoEmail",
                                                image=context.tasker.controller.post_screencap().wait().get(),
                                                pipeline_override={"RecoEmail":{"recognition":"OCR",
                                                                                    "expected": "邮件",
                                                                                    "roi":[0, 494, 180, 168]}})
            if RecoEmail != None:
                context.tasker.controller.post_click(40, 580)
                logger.info("正在进入邮箱")
                time.sleep(1)

            RecoEmailReceive = context.run_recognition("RecoEmailReceive",
                                                image=context.tasker.controller.post_screencap().wait().get(),
                                                pipeline_override={"RecoEmailReceive":{"recognition":"OCR",
                                                                                    "expected": "全部领取",
                                                                                    "roi":[0, 522, 553, 198]}})
            if RecoEmailReceive != None:
                time.sleep(2)
                context.tasker.controller.post_click(115, 670)
                logger.info("正在执行领取邮件")
                
                time.sleep(2)
                RecoEmailObtain = context.run_recognition("RecoEmailObtain",
                                                image=context.tasker.controller.post_screencap().wait().get(),
                                                pipeline_override={"RecoEmailObtain":{"recognition":"OCR",
                                                                                    "expected": "获得物资",
                                                                                    }})
                if RecoEmailObtain != None:
                    context.tasker.controller.post_click(210, 380)
                    logger.info("正在领取邮箱")
                    

                elif RecoEmailObtain == None:
                    RecoEmailHome = context.run_recognition("RecoEmailHome",
                                                    image=context.tasker.controller.post_screencap().wait().get(),
                                                    pipeline_override={"RecoEmailHome":{"recognition":"TemplateMatch",
                                                                                        "template": "Startup/10.png",
                                                                                        "roi":[161, 0, 156, 165]}})
                    if RecoEmailHome != None:
                        context.tasker.controller.post_click(240, 35)
                        logger.info("正在返回主页")

            elif RecoEmailReceive == None:
                time.sleep(1)
                RecoEmailHome = context.run_recognition("RecoEmailHome",
                                                    image=context.tasker.controller.post_screencap().wait().get(),
                                                    pipeline_override={"RecoEmailHome":{"recognition":"TemplateMatch",
                                                                                        "template": "Startup/10.png",
                                                                                        "roi":[161, 0, 156, 165]}})
                if RecoEmailHome != None:
                    time.sleep(1) 
                    context.tasker.controller.post_click(240, 35)
                    logger.info("正在返回主页")
                
            Homepage = context.run_recognition("Homepage",
                                                    image=context.tasker.controller.post_screencap().wait().get(),
                                                    pipeline_override={"Homepage":{"recognition":"TemplateMatch",
                                                                                        "template": "Startup/11.png",
                                                                                        "roi":[852, 288, 276, 314]}})
            if Homepage != None:
                logger.info("已成功返回主页，准备执行下一任务或结束程序")
                return True
            
            

