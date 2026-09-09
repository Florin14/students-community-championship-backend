from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import declarative_base

BaseModel = declarative_base()

# BIGINT primary keys on Postgres; plain INTEGER on sqlite so autoincrement works
# during local smoke-tests.
BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class SqlBaseModel(BaseModel):
    __abstract__ = True

    def update(self, data, exclude=None):
        """Apply the set fields of a Pydantic model onto this instance.

        `exclude` skips fields that need their own handling - a password that
        must go through a hashing setter, for instance - so callers do not have
        to reimplement this loop.
        """
        fields = data.model_dump(
            exclude_unset=True, exclude=set(exclude) if exclude else None
        )
        for key, value in fields.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self
