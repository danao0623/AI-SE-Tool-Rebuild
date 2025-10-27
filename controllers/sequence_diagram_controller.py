from models.sequence_diagram import SequenceDiagram
from controllers.base_controller import BaseController  

class SequenceDiagramController(BaseController):
    model = SequenceDiagram   # 指定這個 Controller 使用的 model 是 SequenceDiagram