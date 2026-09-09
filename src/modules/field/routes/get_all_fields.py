from fastapi import Depends
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from modules.field.models import FieldListResponse, FieldModel

from .router import router


@router.get("/", response_model=FieldListResponse)
async def get_all_fields(db: Session = Depends(get_db)):
    """Public: the fields the championship is played on."""
    fields = db.query(FieldModel).order_by(FieldModel.name).all()
    return FieldListResponse(data=fields)
