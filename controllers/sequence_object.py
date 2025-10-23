from models.sequence_object import SequenceObject
from controllers.base import BaseController

class SequenceObjectController(BaseController):
    model = SequenceObject   # 指定這個 Controller 使用的 model 是 SequenceObject