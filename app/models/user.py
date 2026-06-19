from sqlalchemy import (  # column defines the column, rest all are datatypes for the columns
    Column,
    DateTime,
    Integer,
    String,
)
from sqlalchemy.orm import relationship  # lets us navigate between related tables
from sqlalchemy.sql import (
    func,  # gives database level functions, like func.now() for timestamp
)

from app.database import (
    Base,  # we import Base from the database, this registers Base class as a table
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    datasets = relationship("Dataset", back_populates="owner")
