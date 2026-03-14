# controllers/object_controller.py
from controllers.base_controller import BaseController
from models.object import Object


class ObjectController(BaseController):
    model = Object

    @classmethod
    async def add_object(
        cls,
        *,
        name: str,
        obj_type: str,
        project_id: int,
        usecase_id: int | None = None,  # ✅ 新增
        description: str | None = None,
        canvas_group_key: str | None = None,
    ) -> Object:
        if canvas_group_key is None and obj_type == "Boundary":
            canvas_group_key = name

        return await cls.add(
            name=name,
            type=obj_type,
            project_id=project_id,
            usecase_id=usecase_id,       # ✅ 寫入
            description=description,
            canvas_group_key=canvas_group_key, 
        )