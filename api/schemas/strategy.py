"""Strategy-related Pydantic models.

Phase 3 (sq-0008-p3-schemas): 完整化版本。

字段来源：
- StrategyCreateRequest / StrategyUpdateRequest: api/main.py L778-794 原 Pydantic 类
  （注意：原版用 `type` 字段和 `version: int`，与 spec 模板略不同，以原版为准保 0 行为变更）
- StrategyDetail / StrategySummary: 推断（基于 /strategies 和 /strategies/{id} 端点 SQL 字段）
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class StrategyCreateRequest(BaseModel):
    """创建策略请求（POST /strategies）

    字段来源：api/main.py L778-786 原 Pydantic 类。
    """
    strategy_id: str = Field(..., description="策略 ID（唯一）")
    name: str = Field(..., description="策略名")
    type: str = Field(..., description="策略类型 turtle/dual-ma/...")
    version: int = Field(1, description="策略版本号（UNIQUE(name, version)）")
    description: str = Field("", description="策略描述")
    params: Dict[str, Any] = Field(default_factory=dict, description="策略参数（dict 形式，存为 params_json）")
    is_active: int = Field(1, description="是否启用 1=active, 0=inactive")
    is_paper: int = Field(1, description="是否纸面交易 1=paper, 0=live")


class StrategyUpdateRequest(BaseModel):
    """更新策略参数请求（PUT /strategies/{strategy_id}）

    字段来源：api/main.py L789-792 原 Pydantic 类。
    """
    params: Dict[str, Any] = Field(..., description="新参数")
    change_reason: str = Field("", description="变更原因")
    changed_by: str = Field("user", description="变更人（user/system/auto）")


class StrategyDetail(BaseModel):
    """策略详情（GET /strategies/{strategy_id}）

    字段来源：strategies 表 SELECT * 返回字段 + params_json 解析。
    """
    strategy_id: str = Field(..., description="策略 ID")
    name: str = Field(..., description="策略名")
    version: int = Field(..., description="版本号")
    type: str = Field(..., description="策略类型")
    description: Optional[str] = Field(None, description="策略描述")
    params: Dict[str, Any] = Field(default_factory=dict, description="策略参数")
    is_active: int = Field(1, description="是否启用")
    is_paper: int = Field(1, description="是否纸面交易")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class StrategySummary(BaseModel):
    """策略摘要（GET /strategies 列表项）

    字段来源：strategies 表 SELECT (核心字段) 返回。
    """
    strategy_id: str = Field(..., description="策略 ID")
    name: str = Field(..., description="策略名")
    version: int = Field(..., description="版本号")
    type: str = Field(..., description="策略类型")
    is_active: int = Field(1, description="是否启用")
    params: Optional[Dict[str, Any]] = Field(None, description="策略参数")
