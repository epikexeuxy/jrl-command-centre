"""Import every model so Base.metadata sees the full schema (Alembic autogenerate relies on this)."""
from app.models.deals import Activity, AIReport, Company, Deal, Note, TaskItem
from app.models.user import Role, User
from app.models.wealth import Benchmark, Client, Holding, Portfolio, Report, Transaction, UploadedFile

__all__ = [
    "Role", "User",
    "Benchmark", "Client", "Holding", "Portfolio", "Report", "Transaction", "UploadedFile",
    "Activity", "AIReport", "Company", "Deal", "Note", "TaskItem",
]
