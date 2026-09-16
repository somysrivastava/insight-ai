from app.models.org import Org
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.dataset import Dataset
from app.models.saved_join import SavedJoin
from app.models.export_job import ExportJob
from app.models.scheduled_report import ScheduledReport
from app.models.alert_rule import AlertRule
from app.models.alert_history import AlertHistory
from app.models.dashboard import Dashboard
from app.models.dashboard_pin import DashboardPin
from app.models.column_mapping import ColumnMapping
from app.models.user import User


# Importing the models here ensures every model is registered on Base
# before Alembic's autogenerate (or anything else) inspects Base.metadata.
