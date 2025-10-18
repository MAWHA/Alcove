from MWATools.MWAController import MWAControllerClass
from MWATools.MWAResource import MWAResourceClass
from MWATools.MWATasker import MWATaskerClass
from MWATools.MWAInterface import interface
from MWATools.MWATaskPipeline import MWATaskPipelineClass
from PyPipeline.CustomActions.StartAction import StartApp
MWAResource = MWAResourceClass()


@MWAResource.resource.custom_action("StartApp")
class StartApp(StartApp):
    ...


if __name__ == '__main__':
    pipeline_override = {
        "MyCustomEntry": {"action": "custom", "custom_action": "StartApp"},
    }
    MWAController = MWAControllerClass()
    MWAController.load_controller()
    MWAController.choose_adb_controller()

    MWATasker = MWATaskerClass()

    adb_controller = MWAController.connect_adb_controller()
    MWATasker.MWATaskerBind(controller=adb_controller, resource=MWAResource.resource)
    task_detail = MWATasker.run_action("MyCustomEntry", pipeline_override)
    # MWATaskPipelineClass = MWATaskPipelineClass()
    # print(MWATaskPipelineClass.add_pipeline('启动'))
    # print(MWATaskPipelineClass.add_pipeline('器者征集',True))
    ...