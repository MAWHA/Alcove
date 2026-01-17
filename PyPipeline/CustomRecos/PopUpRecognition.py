from maa.custom_recognition import CustomRecognition

from maa.context import Context
from MWATools.MWALogging import logger
import time

class PopUpRecognition(CustomRecognition):
    def analyze(
        self,
        context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:
        reco_detail = context.run_recognition(
            "MyCustomOCR",
            argv.image,
            pipeline_override={
                "MyCustomOCR": {"recognition": "TemplateMatch", 
                                "template": ["popup/popup.png"],
                                "roi": [90,78,1098,595]}
            },
        )
        if reco_detail:
            context.run_task("popup_cleanup",pipeline_override={"popup_cleanup":{"action":"Click", "target":[1133,99,25,26]}})
        return CustomRecognition.AnalyzeResult(
            box=reco_detail.best_result.box, detail="弹窗已关闭"
        )
