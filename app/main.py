from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.database import Base, engine
from app.routers.health import router as health_router
from app.routers.telegram import router as telegram_router
from app.routers.travelline import router as travelline_router
from app.routers.ttlock import router as ttlock_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(travelline_router)
app.include_router(telegram_router)
app.include_router(ttlock_router)
