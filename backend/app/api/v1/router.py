from fastapi import APIRouter

from app.modules.authentication.router import router as auth_router
from app.modules.catalog.router import admin as catalog_admin
from app.modules.catalog.router import public as catalog_public
from app.modules.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(catalog_public)
api_router.include_router(catalog_admin)
