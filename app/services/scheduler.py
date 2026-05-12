from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from app.database import engine
from app.models import Source


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(_refresh_job, "interval", days=1, id="refresh_sources", replace_existing=True)
    scheduler.start()
    return scheduler


def _refresh_job() -> None:
    from app.main import refresh_content_source

    with Session(engine) as session:
        for source in session.exec(select(Source)).all():
            refresh_content_source(session, source)
        session.commit()
