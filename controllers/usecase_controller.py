from models.usecase import Usecase
from controllers.base_controller import BaseController

class PriceController(BaseController):
    model = Usecase  # 指定這個 Controller 使用的 model 是 Usecase