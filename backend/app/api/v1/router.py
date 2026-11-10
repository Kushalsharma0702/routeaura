from fastapi import APIRouter

from app.modules.authentication.router import router as auth_router
from app.modules.catalog.router import admin as catalog_admin
from app.modules.catalog.router import public as catalog_public
from app.modules.context.router import router as context_router
from app.modules.itinerary.router import router as itineraries_router
from app.modules.recommendations.router import interactions as interactions_router
from app.modules.recommendations.router import router as recommendations_router
from app.modules.routing.router import router as optimization_router
from app.modules.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(catalog_public)
api_router.include_router(catalog_admin)
api_router.include_router(recommendations_router)
api_router.include_router(interactions_router)
api_router.include_router(itineraries_router)
api_router.include_router(optimization_router)
api_router.include_router(context_router)
