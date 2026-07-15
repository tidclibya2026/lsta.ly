from fastapi import APIRouter

from .registry import router as registry_router
from .review import router as review_router
from .search import router as search_router

router = APIRouter()
router.include_router(review_router)
router.include_router(registry_router)
router.include_router(search_router)

__all__ = ["router"]
