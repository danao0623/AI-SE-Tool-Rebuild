from models.event import Event
from controllers.base_controller import BaseController

class EventController(BaseController):
    model = Event  # 指定這個 Controller 使用的 model 是 Event