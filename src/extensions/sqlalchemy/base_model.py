from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import declarative_base

BaseModel = declarative_base()

# BIGINT primary keys on Postgres; plain INTEGER on sqlite so autoincrement works
# during local smoke-tests.
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class SqlBaseModel(BaseModel):
    __abstract__ = True

    def update(self, data):
        """Apply the set fields of a Pydantic model onto this instance."""
        for key, value in data.model_dump(exclude_unset=True).items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self
