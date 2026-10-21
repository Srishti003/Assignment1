from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# Handle Postgres URL format (e.g., Render/Heroku provide postgres:// which SQLAlchemy 2.x expects as postgresql://)
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Request-scoped database session dependency (equivalent to Scoped DbContext in ASP.NET Core)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
