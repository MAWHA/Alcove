from maa.custom_action import CustomAction
from maa.context import Context
from maa.pipeline import JRecognitionType, JOCR
from MWATools.MWALogging import logger
import time

class OpenRecruitment(CustomAction):
    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:
        time.sleep(2)
        if context.run_recognition_direct(JRecognitionType.OCR, 
                                          JOCR(expected="器者征集",roi=[894,532,197,74]),
                                          image=context.tasker.controller.post_screencap().wait().get()).hit:
            self._entry_openrecruitment(context, argv)
        if context.run_recognition_direct(JRecognitionType.OCR, 
                                          JOCR(expected="全部确认",roi=[992,602,230,75]),
                                          image=context.tasker.controller.post_screencap().wait().get()).hit:
            self._confirm_openrecruitment(context, argv)

        _, openrecruitmenting, openrecruitmented, openrecruitment_letter = self._scan_openrecruitment_data(context, argv)

        if openrecruitmented == "0" and openrecruitmenting != "4" and openrecruitment_letter != "0":
            self._start_openrecruitment(context, argv)
            self._return_home(context, argv)
            return True
        elif openrecruitmenting == "4":
            logger.info("器者征集已满")
            self._return_home(context, argv)
            return True
        elif openrecruitmented != "0":
            logger.info("器者征集可领取")
            self._confirm_openrecruitment(context, argv)
            self._return_home(context, argv)
            return True
        else:
            self._return_home(context, argv)
            return True
    def _entry_openrecruitment(
        self, 
        context: Context,
        argv: CustomAction.RunArg
    ):
        logger.info("打开器者征集界面")
        entry_openrecruitment = context.run_task("entry_openrecruitment", 
                                                 pipeline_override={"entry_openrecruitment":{
                                                                    "roi": [904,540,176,58],
                                                                    "recognition": "OCR",
                                                                    "expected": "器者征集",
                                                                    "action": "Click",
                                                                    }})
    def _scan_openrecruitment_data(
        self,
        context: Context,
        argv: CustomAction.RunArg
        ):
        openrecruitment_data = []
        time.sleep(2)
        openrecruitment_queue = context.run_recognition("openrecruitment_data",
                                image=context.tasker.controller.post_screencap().wait().get(),
                                pipeline_override={"openrecruitment_data":{
                                                                "roi": [1171,84,79,50],
                                                                "recognition": "OCR",
                                                                "only_rec": True}})
        if openrecruitment_queue.hit:
            openrecruitment_queue = openrecruitment_queue.best_result.text
            openrecruitment_data.append(openrecruitment_queue)
        openrecruitmenting = context.run_recognition("openrecruitmenting",
                            image=context.tasker.controller.post_screencap().wait().get(),
                            pipeline_override={"openrecruitmenting":{
                                                            "roi": [1169,129,71,42],
                                                            "recognition": "OCR",
                                                            "only_rec": True}})
        if openrecruitmenting.hit:
            openrecruitmenting = openrecruitmenting.best_result.text[0]
            openrecruitment_data.append(openrecruitmenting)
        openrecruitmented = context.run_recognition("openrecruitmented",
                            image=context.tasker.controller.post_screencap().wait().get(),
                            pipeline_override={"openrecruitmented":{
                                                            "roi": [1165,168,79,50],
                                                            "recognition": "OCR",
                                                            "only_rec": True}})
        if openrecruitmented.hit:
            openrecruitmented = openrecruitmented.best_result.text[0]
            openrecruitment_data.append(openrecruitmented)
        openrecruitment_letter = context.run_recognition("openrecruitment_letter",
                                image=context.tasker.controller.post_screencap().wait().get(),
                                pipeline_override={"openrecruitment_letter":{
                                                                "roi": [705,6,73,42],
                                                                "recognition": "OCR",
                                                                "replace": ["。", "0"],
                                                                "expected": r"(\d+)",
                                                                "only_rec": True}})
        if openrecruitment_letter.hit:
            openrecruitment_letter = openrecruitment_letter.best_result.text
            openrecruitment_data.append(openrecruitment_letter)

        logger.info(f"器者征集数据: 征集队列 {openrecruitment_queue}, 征集中 {openrecruitmenting}, 已征集 {openrecruitmented}, 当前信件 {openrecruitment_letter}")
        return openrecruitment_data
    def _start_openrecruitment(
        self,
        context: Context,
        argv: CustomAction.RunArg
        ):
        logger.info("开始器者征集")
        context.run_task("start_openrecruitment", pipeline_override={"start_openrecruitment":{
                                                                "roi": [1044,622,143,48],
                                                                "recognition": "OCR",
                                                                "expected": "开始征集",
                                                                "action": "Click"
                                                                }})
        choose_click_box = context.run_recognition("choose_openrecruitment_count", 
                                                   image=context.tasker.controller.post_screencap().wait().get(),
                                                   pipeline_override={"choose_openrecruitment_count":{
                                                                "roi": [744,324,48,46],
                                                                "recognition": "OCR",
                                                                "expected": "\+"}}).best_result.box
        for i in range(4):
            context.tasker.controller.post_click(choose_click_box[0]+24, choose_click_box[1]+23)
            time.sleep(0.5)
        choose_finish_box = context.run_task("choose_openrecruitment_count", 
                                                   pipeline_override={"choose_openrecruitment_count":{
                                                                "roi": [672,394,190,89],
                                                                "recognition": "TemplateMatch",
                                                                "template": "collect/04.png",
                                                                "action": "Click"}})
        
    def _confirm_openrecruitment(
        self,
        context: Context,
        argv: CustomAction.RunArg
        ):
        logger.info("正在确认器者征集")
        context.run_task("switch_to_openrecruitment_queue", pipeline_override={"switch_to_openrecruitment_queue":{
                                                                "roi": [1169,301,75,116],
                                                                "recognition": "TemplateMatch",
                                                                "template": "collect/02.png",
                                                                "action": "Click"
                                                                }})
        time.sleep(0.5)
        context.run_task("confirm_openrecruitment", pipeline_override={"confirm_openrecruitment":{
                                                                "roi": [1034,613,136,51],
                                                                "recognition": "OCR",
                                                                "expected": "全部确认",
                                                                "action": "Click"}})
        time.sleep(0.5)
        context.run_task("confirm_openrecruitment_skip", pipeline_override={"confirm_openrecruitment_skip":{
                                                                "action": "Click",
                                                                "target": [1157,12,83,73]}})
        time.sleep(1)
        context.run_task("confirm_openrecruitment_again", pipeline_override={"confirm_openrecruitment_again":{
                                                                "roi": [520,579,250,83],
                                                                "recognition": "TemplateMatch",
                                                                "template": "collect/04.png",
                                                                "action": "Click"}})
        detail = context.run_task("dian",
                                pipeline_override={"dian":{"recognition": "OCR",
                                                                    "expected": "点",
                                                                    "roi":[978,106,240,502],
                                                                    "next":"ji"},
                                                    "ji":{"recognition": "OCR",
                                                                    "expected": "击",
                                                                    "roi":[978,106,240,502],
                                                                    "action": "Click"}})
    def _return_home(
        self,
        context: Context,
        argv: CustomAction.RunArg
        ):
        context.run_task("return_home", pipeline_override={"return_home":{
                                                           "action": "Custom",
                                                           "custom_action": "ReturnHome"}})