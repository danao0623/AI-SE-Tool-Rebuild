from models.event_list import EventList
from controllers.base_controller import BaseController

class EventListController(BaseController):
    model = EventList  # 指定這個 Controller 使用的 model 是 EventList