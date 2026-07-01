"""装配体相关 Pydantic schema。

覆盖 PartIteration 更新（写入 components + cadInstances）
和装配实例查询（矩阵合成结果响应）。
"""
from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.part import _to_camel


# ---------------------------------------------------------------------------
# 通用配置基类
# ---------------------------------------------------------------------------

class _OrmBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=_to_camel,
        populate_by_name=True,
    )


class _RequestBase(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )


# ---------------------------------------------------------------------------
# CADInstance schema
# ---------------------------------------------------------------------------

class CADInstanceCreate(_RequestBase):
    """
    单个 CAD 实例的位置信息。
    ANGLE 模式：传入 rx/ry/rz（弧度）
    MATRIX 模式：传入 matrix（9 个 double，行优先 3×3 旋转矩阵）+ tx/ty/tz
    """
    rotation_type: str = Field("ANGLE", description="ANGLE 或 MATRIX")
    tx: float = Field(0.0, description="X 轴平移量（毫米）")
    ty: float = Field(0.0, description="Y 轴平移量（毫米）")
    tz: float = Field(0.0, description="Z 轴平移量（毫米）")
    # ANGLE 模式：欧拉角（弧度）
    rx: Optional[float] = Field(None, description="ANGLE 模式：X 轴旋转角（弧度）")
    ry: Optional[float] = Field(None, description="ANGLE 模式：Y 轴旋转角（弧度）")
    rz: Optional[float] = Field(None, description="ANGLE 模式：Z 轴旋转角（弧度）")
    # MATRIX 模式：9 个 double，行优先
    matrix: Optional[list[float]] = Field(
        None,
        min_length=9,
        max_length=9,
        description="MATRIX 模式：3×3 旋转矩阵（行优先，9 个 double）",
    )
    # 在 usage_link 中的排序
    order: int = Field(0, description="实例在同一 usage_link 中的排列顺序")


class CADInstanceResponse(_OrmBase):
    id: uuid.UUID
    usage_link_id: uuid.UUID
    rotation_type: str
    tx: float
    ty: float
    tz: float
    rx: Optional[float] = None
    ry: Optional[float] = None
    rz: Optional[float] = None
    m00: Optional[float] = None
    m01: Optional[float] = None
    m02: Optional[float] = None
    m10: Optional[float] = None
    m11: Optional[float] = None
    m12: Optional[float] = None
    m20: Optional[float] = None
    m21: Optional[float] = None
    m22: Optional[float] = None
    order: int


# ---------------------------------------------------------------------------
# PartUsageLink schema
# ---------------------------------------------------------------------------

class UsageLinkCreate(_RequestBase):
    """
    一条装配 BOM 行（父迭代使用一个子零件）。
    component.number 为子零件编号（在同一 workspace_id 下查找）。
    """
    component_number: str = Field(..., description="子零件编号")
    amount: float = Field(1.0, gt=0, description="用量")
    unit: Optional[str] = Field(None, max_length=20, description="单位，如 ea / mm")
    optional: bool = Field(False, description="是否可选件")
    order: int = Field(0, description="在父装配体中的子件排序")
    comment: Optional[str] = Field(None, description="备注")
    cad_instances: list[CADInstanceCreate] = Field(
        default_factory=list,
        description="该子件在父装配体中的所有位置实例（可多个，表示重复使用）",
    )


class UsageLinkResponse(_OrmBase):
    id: uuid.UUID
    parent_iteration_id: uuid.UUID
    component_master_id: uuid.UUID
    amount: float
    unit: Optional[str] = None
    optional: bool
    order: int
    comment: Optional[str] = None
    cad_instances: list[CADInstanceResponse] = []


# ---------------------------------------------------------------------------
# PartIteration 更新请求
# ---------------------------------------------------------------------------

class IterationUpdateRequest(_RequestBase):
    """
    PUT /api/parts/{number}/{version}/iterations/{iteration} 的请求体。
    对应 DocDoku PartResource.updatePartIteration()。
    """
    iteration_note: Optional[str] = Field(None, description="本次迭代备注")
    components: list[UsageLinkCreate] = Field(
        default_factory=list,
        description="装配体子件列表（含位置信息），覆盖写入（先删旧的再写新的）",
    )


class IterationUpdateResponse(_OrmBase):
    """PartIteration 更新后的完整响应。"""
    id: uuid.UUID
    part_revision_id: uuid.UUID
    iteration: int
    iteration_note: Optional[str] = None
    check_in_date: Optional[str] = None
    components: list[UsageLinkResponse] = []


# ---------------------------------------------------------------------------
# 矩阵合成接口响应（2.3）
# ---------------------------------------------------------------------------

class InstanceResponse(BaseModel):
    """
    单个零件实例的全局变换矩阵和包围盒。
    matrix：16 个 double，行优先 4×4 齐次变换矩阵（全局世界坐标系）。
    前端直接 mesh.applyMatrix4(matrix) 即可。
    """
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    # 实例标识
    id: str = Field(..., description="实例路径 ID，如 'u1-1:u2-3'")
    part_number: str = Field(..., description="零件编号")
    version: str = Field(..., description="版本号")
    iteration: int = Field(..., description="迭代号")

    # 全局 4×4 变换矩阵（16 个 double，行优先）
    matrix: list[float] = Field(..., min_length=16, max_length=16)

    # 包围盒（毫米，可选，转换完成前为 None）
    x_min: Optional[float] = None
    y_min: Optional[float] = None
    z_min: Optional[float] = None
    x_max: Optional[float] = None
    y_max: Optional[float] = None
    z_max: Optional[float] = None

    # 几何文件路径（最高 LOD）
    geometry_full_name: Optional[str] = None
