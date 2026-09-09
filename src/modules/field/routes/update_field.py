from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.field.models import FieldModel, FieldResponse, FieldUpdate

from .router import router


@router.put(
    "/{id}",
    response_model=FieldResponse,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def update_field(
    data: FieldUpdate,
    field: FieldModel = Depends(GetInstanceFromPath(FieldModel)),
    db: Session = Depends(get_db),
):
    if data.name is not None and data.name != field.name:
        taken = (
            db.query(FieldModel)
            .filter(FieldModel.name == data.name, FieldModel.id != field.id)
            .first()
        )
        if taken is not None:
            raise ErrorException(
                Error.CONFLICT,
                message="A field with this name already exists",
                status_code=status.HTTP_409_CONFLICT,
            )

    field.update(data)
    db.commit()
    db.refresh(field)
    return field
