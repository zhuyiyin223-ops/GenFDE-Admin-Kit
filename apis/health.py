"""API 健康检查。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends

from apis import get_current_client


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", dependencies=[Depends(get_current_client)])
async def health():
    """API 接口健康测试。"""
    return {
        "message": "hello world",
        "timestamp": datetime.now().isoformat(),
    }
