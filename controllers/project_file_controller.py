from models.project_file import ProjectFile
from controllers.base_controller import BaseController

class ProjectFileController(BaseController):
    model = ProjectFile   # 指定這個 Controller 使用的 model 是 Attribute