from models.usecase_actor import UsecaseActor
from controllers.base import BaseController

class UsecaseActorController(BaseController):
    model = UsecaseActor  # 指定這個 Controller 使用的 model 是 UsecaseActor