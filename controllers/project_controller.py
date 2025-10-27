from models.project import Project
from controllers.base_controller import BaseController

class ProjectController(BaseController):
    model = Project  # 指定這個 Controller 使用的 model 是 Project

   
    