from maa.resource import Resource
# 从interface加载资源路径（picli）

class MWAResourceClass():
    def __init__(self, resource_path: str = "./assets/resource_picli/base"):
        """初始化资源(pipeline/model/image)"""
        self.resource_path = resource_path
        self.resource = Resource()
        self.res_job = self.resource.post_bundle(self.resource_path)
        self.res_job.wait()


if __name__ == "__main__":
    MWAResource = MWAResourceClass()
    print(MWAResource.resource_path)