from fastapi import APIRouter

from .discovery import router as discovery_router
from .executive import router as executive_router
from .media_review import router as media_review_router
from .metadata import router as metadata_router
from .registry import router as registry_router
from .review import router as review_router
from .search import router as search_router

router = APIRouter()
router.include_router(review_router)
router.include_router(registry_router)
router.include_router(search_router)
router.include_router(metadata_router)
router.include_router(media_review_router)
router.include_router(discovery_router)
router.include_router(executive_router)

__all__ = ["router"]
