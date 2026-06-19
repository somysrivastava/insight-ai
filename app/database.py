from sqlalchemy import create_engine  # this is the engine to connect to postgres
from sqlalchemy.orm import (
    declarative_base,  # this is the base class for all models
    sessionmaker,  # this is the sessionmaker to create sessions, (gives workspace)
)

Base = declarative_base()
DATABASE_URL = "postgresql://postgres:password@localhost:5432/insightai"

engine = create_engine(
    DATABASE_URL, echo=True
)  # echo=true prints every sql query sqlalchemy executes

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# SessionLocal is NOT a session yet — it's a class that MAKES sessions
# autocommit=False → we must manually call session.commit() to save changes
# autoflush=False  → don't auto-send SQL until we commit
# bind=engine      → which database to connect to


def get_db():
    db = SessionLocal()  # fresh session open kiya
    try:
        yield db  # hand it to the route function
    finally:
        db.close()  # always close it
