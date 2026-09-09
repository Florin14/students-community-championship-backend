from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.field.models import FieldModel
from modules.match.models import MatchModel

from .router import router


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def delete_field(
    field: FieldModel = Depends(GetInstanceFromPath(FieldModel)),
    db: Session = Depends(get_db),
):
    scheduled = (
        db.query(MatchModel).filter(MatchModel.fieldId == field.id).count()
    )
    if scheduled:
        raise ErrorException(
            Error.BAD_REQUEST,
            message=(
                f"{scheduled} match(es) are scheduled on this field; "
                "move them first"
            ),
        )

    db.delete(field)
    db.commit()
    return None
