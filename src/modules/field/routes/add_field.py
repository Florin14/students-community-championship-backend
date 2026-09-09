from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.field.models import FieldAdd, FieldModel, FieldResponse

from .router import router


@router.post(
    "/",
    response_model=FieldResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def add_field(data: FieldAdd, db: Session = Depends(get_db)):
    exists = db.query(FieldModel).filter(FieldModel.name == data.name).first()
    if exists is not None:
        raise ErrorException(
            Error.CONFLICT,
            message="A field with this name already exists",
            status_code=status.HTTP_409_CONFLICT,
        )

    field = FieldModel(
        name=data.name,
        shortName=data.shortName,
        location=data.location,
        description=data.description,
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    return field
