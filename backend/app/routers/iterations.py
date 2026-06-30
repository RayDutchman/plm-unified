"""零件迭代相关 API 路由（M2 Phase A + B）。

端点：
  PUT  /api/parts/{number}/{version}/iterations/{iteration}
       更新迭代的装配子件（components + cadInstances），覆盖写入

  GET  /api/parts/{number}/{version}/instances
       零件级快速预览：递归装配树，返回所有叶子零件的全局 mat4

  PUT  /api/parts/{number}/{version}/iterations/{iteration}/nativecad
       上传原生 CAD 文件（写入 vault），自动触发 Kafka 转换消息

  PUT  /api/parts/{number}/{version}/iterations/{iteration}/conversion
       conversion 服务回调（写入 geometry + 更新转换状态）

  GET  /api/parts/{number}/{version}/iterations/{iteration}/conversion
       查询转换状态（pending / succeed / startDate / endDate）
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Query, Request, UploadFile
from pydantic import BaseModel, ConfigDict

from app.schemas.part import _to_camel
from sqlalchemy.orm import Session

from app.crud.assembly import compute_instances, write_components
from app.crud.conversion import (
    get_conversion_status,
    handle_conversion_callback,
    publish_conversion_order,
    save_native_cad_file,
)
from app.database import get_db
from app.models import User
from app.routers.auth import get_current_active_user
from app.schemas.assembly import (
    InstanceResponse,
    IterationUpdateRequest,
    IterationUpdateResponse,
    UsageLinkResponse,
    CADInstanceResponse,
)

router = APIRouter(prefix="/api/parts", tags=["零件迭代 / 装配体"])


@router.put(
    "/{number}/{version}/iterations/{iteration}",
    response_model=IterationUpdateResponse,
    summary="更新迭代装配内容（components + cadInstances）",
)
def update_iteration_components(
    number: str,
    version: str,
    iteration: int,
    body: IterationUpdateRequest,
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    覆盖写入一个迭代的装配子件列表（components + cadInstances）。

    - 迭代必须处于 WIP 且由当前用户签出
    - 先删除该迭代所有旧 usage_links（cad_instances 级联删除）
    - 再逐条写入新的 usage_links + cad_instances
    - 子件编号在同一 workspace 内查找

    对应 DocDoku PartResource.updatePartIteration() + createComponents()
    """
    iteration_orm = write_components(
        db=db,
        number=number,
        version=version,
        iteration_number=iteration,
        workspace_id=workspace_id,
        current_user_id=current_user.id,
        components=body.components,
        iteration_note=body.iteration_note,
    )

    # 手动组装响应（避免 N+1 lazy load 问题）
    from app.models.assembly import CADInstance, PartUsageLink
    from datetime import datetime

    usage_links_orm = (
        db.query(PartUsageLink)
        .filter(PartUsageLink.parent_iteration_id == iteration_orm.id)
        .order_by(PartUsageLink.order)
        .all()
    )

    links_resp = []
    for link in usage_links_orm:
        cad_insts = (
            db.query(CADInstance)
            .filter(CADInstance.usage_link_id == link.id)
            .order_by(CADInstance.order)
            .all()
        )
        link_r = UsageLinkResponse.model_validate(link)
        link_r.cad_instances = [CADInstanceResponse.model_validate(ci) for ci in cad_insts]
        links_resp.append(link_r)

    check_in_str = (
        iteration_orm.check_in_date.isoformat()
        if iteration_orm.check_in_date else None
    )
    return IterationUpdateResponse(
        id=iteration_orm.id,
        part_revision_id=iteration_orm.part_revision_id,
        iteration=iteration_orm.iteration,
        iteration_note=iteration_orm.iteration_note,
        check_in_date=check_in_str,
        components=links_resp,
    )


@router.get(
    "/{number}/{version}/instances",
    response_model=list[InstanceResponse],
    summary="查询零件的所有叶子实例及全局变换矩阵",
)
def get_part_instances(
    number: str,
    version: str,
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    config_spec: str = Query("latest", description="配置规格，目前仅支持 latest"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    递归遍历装配树，层层累乘 mat4，返回每个叶子零件的全局 4×4 变换矩阵。

    - matrix：16 个 double，行优先，前端直接 mesh.applyMatrix4(matrix)
    - 叶子节点 = 无 usage_links 的迭代（即单个零件，非装配体）
    - config_spec=latest：取最新签入迭代（RELEASED 优先，次选 WIP）
    """
    return compute_instances(
        db=db,
        root_number=number,
        root_version=version,
        workspace_id=workspace_id,
        config_spec=config_spec,
    )


# ---------------------------------------------------------------------------
# 2.5 CAD 文件上传
# ---------------------------------------------------------------------------

@router.put(
    "/{number}/{version}/iterations/{iteration}/nativecad",
    summary="上传原生 CAD 文件（触发转换）",
)
async def upload_native_cad(
    number: str,
    version: str,
    iteration: int,
    file: UploadFile = File(..., description="原生 CAD 文件（.stp/.step/.igs 等）"),
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    workspace_name: str = Query(..., description="工作空间名称（用于 vault 路径）"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    上传原生 CAD 文件到 vault，并向 Kafka CONVERT topic 发送转换任务。

    - 迭代必须处于签出状态且签出用户为当前用户
    - vault 路径：{workspace}/parts/{number}/{version}/{iter}/nativecad/{filename}
    - 上传后自动触发异步转换，通过 GET .../conversion 轮询状态
    """
    br = await save_native_cad_file(
        db=db,
        number=number,
        version=version,
        iteration_number=iteration,
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        current_user_id=current_user.id,
        file=file,
    )

    # 获取当前用户的 JWT token 传给 conversion 服务（用于回调鉴权）
    auth_header = request.headers.get("Authorization", "") if request else ""
    user_token = auth_header.replace("Bearer ", "").strip()

    # 发 Kafka 消息（fire-and-forget，失败不影响上传本身）
    try:
        await publish_conversion_order(
            workspace_name=workspace_name,
            number=number,
            version=version,
            iteration_number=iteration,
            full_name=br.full_name,
            file_size=br.content_length,
            user_token=user_token,
        )
    except Exception:
        # Kafka 不可用时不阻塞文件上传，conversion 可手动重试
        pass

    return {
        "fullName": br.full_name,
        "contentLength": br.content_length,
        "message": "文件上传成功，已发送转换任务",
    }


# ---------------------------------------------------------------------------
# 2.7 转换回调（conversion 服务调用）
# ---------------------------------------------------------------------------

class ConversionCallbackBody(BaseModel):
    """conversion 服务回调请求体。同时接受 camelCase 和 snake_case 字段名。"""
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    succeed: bool
    geometry_full_name: Optional[str] = None
    x_min: Optional[float] = None
    y_min: Optional[float] = None
    z_min: Optional[float] = None
    x_max: Optional[float] = None
    y_max: Optional[float] = None
    z_max: Optional[float] = None
    quality: int = 0
    content_length: int = 0


@router.put(
    "/{number}/{version}/iterations/{iteration}/conversion",
    summary="转换服务回调（写入 geometry + 更新状态）",
)
def conversion_callback(
    number: str,
    version: str,
    iteration: int,
    body: ConversionCallbackBody,
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    由 conversion 容器在转换完成后调用。

    - succeed=true：写入 BinaryResource + Geometry 记录
    - succeed=false：仅更新 Conversion 状态为失败
    - 对应 DocDoku ConverterBean.handleConversionResultCallback()
    """
    conversion = handle_conversion_callback(
        db=db,
        number=number,
        version=version,
        iteration_number=iteration,
        workspace_id=workspace_id,
        succeed=body.succeed,
        geometry_full_name=body.geometry_full_name,
        x_min=body.x_min, y_min=body.y_min, z_min=body.z_min,
        x_max=body.x_max, y_max=body.y_max, z_max=body.z_max,
        quality=body.quality,
        content_length=body.content_length,
    )
    return {
        "pending": conversion.pending,
        "succeed": conversion.succeed,
        "message": "转换结果已记录",
    }


# ---------------------------------------------------------------------------
# 2.8 转换状态查询
# ---------------------------------------------------------------------------

@router.get(
    "/{number}/{version}/iterations/{iteration}/conversion",
    summary="查询 CAD 转换状态",
)
def get_conversion(
    number: str,
    version: str,
    iteration: int,
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    查询迭代的 CAD 文件转换状态。

    返回：{pending, succeed, startDate, endDate}
    - pending=true：转换进行中，请继续轮询
    - pending=false, succeed=true：转换成功，可签入
    - pending=false, succeed=false：转换失败，可重试上传
    """
    return get_conversion_status(
        db=db,
        number=number,
        version=version,
        iteration_number=iteration,
        workspace_id=workspace_id,
    )
