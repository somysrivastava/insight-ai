from app.models.org import Org
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.dataset import Dataset
from app.models.saved_join import SavedJoin
from app.models.export_job import ExportJob
from app.models.scheduled_report import ScheduledReport
from app.models.user import User


# Importing the models here ensures every model is registered on Base
# before Alembic's autogenerate (or anything else) inspects Base.metadata.
