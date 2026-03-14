from models.attribute import Attribute
from controllers.base_controller import BaseController

class AttributeController(BaseController):
    model = Attribute

    @classmethod
    async def add_attribute(
        cls,
        *,
        object_id: int,
        name: str,
        type: str | None = None,
        visibility: str | None = "public",
    ):
        return await cls.add(
            object_id=object_id,
            name=name,
            type=type,
            visibility=visibility,
        )
