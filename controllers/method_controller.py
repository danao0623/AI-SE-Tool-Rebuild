from models.method import Method
from controllers.base_controller import BaseController

class MethodController(BaseController):
    model = Method   # 指定這個 Controller 使用的 model 是 Method