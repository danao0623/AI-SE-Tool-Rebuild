from models.method import Method
from controllers.base_controller import BaseController

class MethodController(BaseController):
    model = Method

    @classmethod
    async def add_method(
        cls,
        *,
        object_id: int,
        name: str,
        parameters: str | None = None,
        return_type: str | None = None,          # ✅ 改這裡
        visibility: str | None = "public",
    ):
        return await cls.add(
            object_id=object_id,
            name=name,
            parameters=parameters,
            return_type=return_type,              # ✅ 改這裡
            visibility=visibility,
        )