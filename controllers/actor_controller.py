from models.actor import Actor
from controllers.base_controller import BaseController

class ActorController(BaseController):
    model = Actor  # 指定這個 Controller 使用的 model 是 Actor