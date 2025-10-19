from maa.custom_action import CustomAction
from maa.context import Context
from maa.define import OCRResult
from MWATools.MWALogging import logger
import time
import random

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
                CloseAnnouncement = context.run_recognition("RecoAnnouncement",
                                                image=context.tasker.controller.post_screencap().wait().get(),
                                                pipeline_override={"RecoAnnouncement":{"recognition": "TemplateMatch",
                                                                                 "template": "Startup/12.png"}})

                x0 = CloseAnnouncement.best_result.box[0]
                y0 = CloseAnnouncement.best_result.box[1]
                w = CloseAnnouncement.best_result.box[2]
                h = CloseAnnouncement.best_result.box[3]

                # 计算x和y的随机取值范围
                x_min = x0 
                x_max = x0+w  
                y_min = y0 
                y_max = y0+h  

                # 如果需要整数坐标（例如像素坐标），用randint：
                random_x = random.randint(int(x_min), int(x_max))
                random_y = random.randint(int(y_min), int(y_max))

                context.tasker.controller.post_click(random_x, random_y)

                
                logger.info("关闭公告")
            
            EntryGame = context.run_recognition("EntryGame",
                                                image=context.tasker.controller.post_screencap().wait().get(),
                                                pipeline_override={"EntryGame":{"recognition": "OCR",
                                                                                 "expected": "壬音"}})
            if EntryGame != None:
                context.tasker.controller.post_click(EntryGame.best_result.box[0],EntryGame.best_result.box[1])
                return True
            
            SignIn = context.run_recognition("SignIn",
                                                image=context.tasker.controller.post_screencap().wait().get(),
                                                pipeline_override={"SignIn":{"recognition": "OCR",
                                                                                 "expected": "请输入手机号"}})

            if SignIn !=None:
                logger.error("登录失败，请用户自行登录")
                return True
            
