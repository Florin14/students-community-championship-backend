from fastapi import Depends, Path, status
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException


class GetInstanceFromPath:
    """Dependency that loads a model instance from the `{id}` path parameter."""

    def __init__(self, model):
        self.model = model

    def __call__(self, id: int = Path(...), db: Session = Depends(get_db)):
        instance = db.query(self.model).filter(self.model.id == id).first()
        if instance is None:
            raise ErrorException(
                Error.NOT_FOUND,
                message=f"{self.model.__name__.replace('Model', '')} not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return instance
