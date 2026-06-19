from app.models.dataset import Dataset
from app.models.user import User


# Importing the models here ensures SQLAlchemy sees them
# when Base.metadata.create_all() runs in main.py
# Without this, the tables might not get created
