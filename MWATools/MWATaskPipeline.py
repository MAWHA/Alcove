from MWATools.MWAReadTask import MWAReadTaskClass

class MWATaskPipelineClass(MWAReadTaskClass):
    def __init__(self):
        self.pipelines = []
        super().__init__()

    def add_pipeline(self, task_name: str, options: bool = False):
        if options:
            self.pipelines.append(self.get_task_entry(task_name))
            self.pipelines.append(self.get_task_options(task_name))
        else:
            self.pipelines.append(self.get_task_entry(task_name))
        return self.pipelines

if __name__ == '__main__':
    MWATaskPipelineClass = MWATaskPipelineClass()
    print(MWATaskPipelineClass.add_pipeline('启动'))
    print(MWATaskPipelineClass.add_pipeline('器者征集',True))