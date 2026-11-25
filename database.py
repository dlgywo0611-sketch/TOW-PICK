from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = "sqlite:///./tow_pick.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def configure_sqlite_connection(connection, _record):
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def ensure_current_candidate_index(db_engine):
    """Add the partial unique index to old DBs without altering their rows."""
    try:
        with db_engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_decision_current_candidate "
                "ON decision_candidates(decision_id) WHERE is_current = 1"
            )
    except IntegrityError as error:
        raise RuntimeError(
            "Existing decisions have multiple current candidates; back up "
            "and resolve them before applying the phase 2 index"
        ) from error


def ensure_notification_attempt_columns(db_engine):
    """Extend an earlier attempt ledger without replacing its existing rows."""
    with db_engine.begin() as connection:
        if db_engine.dialect.name != "sqlite":
            return
        names = {row[1] for row in connection.exec_driver_sql(
            "PRAGMA table_info(notification_dispatch_attempts)")}
        if not names:
            return
        if "mode" not in names:
            connection.exec_driver_sql(
                "ALTER TABLE notification_dispatch_attempts "
                "ADD COLUMN mode VARCHAR(20) NOT NULL DEFAULT 'mock'")
        if "provider_message_id" not in names:
            connection.exec_driver_sql(
                "ALTER TABLE notification_dispatch_attempts "
                "ADD COLUMN provider_message_id VARCHAR(255)")

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
