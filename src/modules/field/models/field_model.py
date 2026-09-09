from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship

from extensions.sqlalchemy import BigIntPK, SqlBaseModel


class FieldModel(SqlBaseModel):
    """A playing surface. Four matches run in parallel, one per field, and an
    operator is assigned to the field they are standing next to.
    """

    __tablename__ = "fields"

    id = Column(BigIntPK, primary_key=True, index=True)
    name = Column(String(80), nullable=False, unique=True)
    shortName = Column("short_name", String(12), nullable=True)
    location = Column(String(160), nullable=True)
    description = Column(Text, nullable=True)

    matches = relationship("MatchModel", back_populates="field")
