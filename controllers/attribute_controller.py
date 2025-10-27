from models.attribute import Attribute
from controllers.base_controller import BaseController

class AttributeController(BaseController):
    model = Attribute   # 指定這個 Controller 使用的 model 是 Attribute