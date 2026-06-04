"""Cross-domain shared schemas (Pydantic models).

Phase 3 (sq-0008-p3-schemas): 完整化版本。
"""
from pydantic import BaseModel, Field
from typing import Optional


class HealthResponse(BaseModel):
    """健康检查响应（GET /health）

    字段来源：api/main.py /health 端点（当前返回简单 dict，
    P3 升级为结构化响应便于客户端解析版本/时间戳/DB 状态）。
    """
    status: str = Field("ok", description="服务状态 ok/degraded/down")
    db_ok: bool = Field(True, description="数据库连接是否正常")
    service: str = Field("stock-quant-api", description="服务名")
    version: str = Field("1.6.0", description="API 版本")
    ts: float = Field(0.0, description="响应时间戳（秒）")


class ApiError(BaseModel):
    """统一错误响应结构（FastAPI HTTPException 兼容）。"""
    error: str = Field(..., description="错误类型 / 简短描述")
    detail: Optional[str] = Field(None, description="详细错误信息")
    code: int = Field(400, description="HTTP 状态码")
