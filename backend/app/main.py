"""Aplikasi FastAPI. Jalankan dengan: uvicorn app.main:app --port 8000

Semua endpoint berada di bawah /api. Dokumentasi interaktif: http://localhost:8000/api/docs
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app import config
from app.api import admin_data, admin_eval, admin_import, auth, public
from app.db import SessionLocal, engine, init_db
from app.search.index_manager import IndexManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(session_factory: sessionmaker | None = None, index_manager: IndexManager | None = None) -> FastAPI:
    """Pabrik aplikasi. Tes memberikan database dan indeks sendiri; server memakai default."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if session_factory is None:  # server sungguhan
            init_db(engine)
            app.state.index_manager.load_active()
            if app.state.index_manager.active is not None:
                # Muat model IndoSBERT di latar belakang agar pencarian pertama tidak menunggu lama.
                threading.Thread(target=lambda: app.state.index_manager.encoder.model, daemon=True).start()
        yield

    app = FastAPI(title=f"{config.APP_NAME} API", version=config.APP_VERSION, lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.state.session_factory = session_factory or SessionLocal
    app.state.index_manager = index_manager or IndexManager(app.state.session_factory)

    api = APIRouter(prefix="/api")

    @api.get("/health", tags=["publik"])
    def health(request: Request) -> JSONResponse:
        """Cek kesehatan. Juga dipanggil cron keep-alive setiap hari (lihat DEPLOY.md): satu panggilan ini
        menyentuh database dan penyimpanan cadangan Supabase, sehingga proyek Supabase tidak dianggap
        "tidak aktif" dan dijeda."""
        result = {"status": "ok", "app": config.APP_NAME, "version": config.APP_VERSION}
        manager = request.app.state.index_manager
        try:
            with request.app.state.session_factory() as session:
                session.execute(text("SELECT 1"))
            result["database"] = "ok"
        except Exception as exc:
            result["status"], result["database"] = "error", type(exc).__name__
        if manager.store is not None:
            try:
                manager.store.ping()
                result["penyimpanan"] = "ok"
            except Exception as exc:
                result["status"], result["penyimpanan"] = "error", type(exc).__name__
        result["indeks"] = manager.active.versi if manager.active else None
        return JSONResponse(result, status_code=200 if result["status"] == "ok" else 503)

    for module in (public, auth, admin_data, admin_import, admin_eval):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()
