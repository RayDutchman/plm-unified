"""
旧 DocDoku 格式的 conversion 回调适配器。

conversion 容器（Quarkus）完成转换后，会按旧 DocDoku API 格式回调：
  PUT /workspaces/{workspaceId}/parts/{partNumber}-{partVersion}/conversion

请求体（ConversionResultDTO JSON-B 序列化）：
  {
    "partIterationKey": {
      "partRevision": {"partMaster": {"workspace": "...", "number": "..."}, "version": "A"},
      "iteration": 1
    },
    "convertedFile": "vault 内的 GLB 相对路径",
    "box": [xMin, yMin, zMin, xMax, yMax, zMax],
    "stdOutput": "...",
    "errorOutput": "..."
  }

此路由将旧格式转换为新 API 的 handle_conversion_callback() 调用。
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.crud.conversion import handle_conversion_callback
from app.database import get_db
from app.models.part import PartMaster, PartRevision, PartIteration

router = APIRouter(prefix="/workspaces", tags=["转换回调（DocDoku 兼容）"])


class _PartMasterKey(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    workspace: Optional[str] = None
    number: Optional[str] = None


class _PartRevisionKey(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    partMaster: Optional[_PartMasterKey] = None
    version: Optional[str] = None


class _PartIterationKey(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    partRevision: Optional[_PartRevisionKey] = None
    iteration: Optional[int] = None


class ConversionResultDTO(BaseModel):
    """旧 DocDoku ConversionResultDTO 格式（JSON-B 序列化，camelCase）。"""
    model_config = ConfigDict(populate_by_name=True)

    partIterationKey: Optional[_PartIterationKey] = None
    convertedFile: Optional[str] = None          # 单文件路径（旧格式兼容）
    convertedFileLODs: Optional[dict] = None      # {quality: filename} Map（新格式）
    box: Optional[list[float]] = None             # [xMin, yMin, zMin, xMax, yMax, zMax]
    tempDir: Optional[str] = None                 # conversion 临时目录名
    stdOutput: Optional[str] = None
    errorOutput: Optional[str] = None


def _find_workspace_id(db: Session, workspace_name: str) -> Optional[uuid.UUID]:
    """按工作空间名称查找 workspace_id。"""
    from app.models.workspace import Workspace
    ws = db.query(Workspace).filter_by(name=workspace_name).first()
    return ws.id if ws else None


def _find_iteration_by_key(
    db: Session,
    workspace_id: uuid.UUID,
    part_number: str,
    version: str,
    iteration_number: int,
) -> Optional[PartIteration]:
    master = db.query(PartMaster).filter_by(workspace_id=workspace_id, number=part_number).first()
    if not master:
        return None
    revision = db.query(PartRevision).filter_by(part_master_id=master.id, version=version).first()
    if not revision:
        return None
    return db.query(PartIteration).filter_by(
        part_revision_id=revision.id, iteration=iteration_number
    ).first()


@router.put(
    "/{workspaceId}/parts/{partNumberVersion}/conversion",
    summary="DocDoku 兼容回调（conversion 容器调用）",
    include_in_schema=True,
)
def legacy_conversion_callback(
    workspaceId: str = Path(..., description="工作空间名称（旧格式用名称而非 UUID）"),
    partNumberVersion: str = Path(..., description="{partNumber}-{partVersion} 格式"),
    body: ConversionResultDTO = None,
    db: Session = Depends(get_db),
):
    """
    适配 conversion 容器（Quarkus）的旧 DocDoku 回调格式。

    从 URL 和 body 里提取 workspace/number/version/iteration 等信息，
    转换为新 API 的 handle_conversion_callback() 调用。
    """
    # 解析 {partNumber}-{partVersion} 格式
    # version 固定是单字母（A/B/C...），用最后一个 "-" 分割
    if "-" not in partNumberVersion:
        raise HTTPException(status_code=400, detail="无效的 partNumberVersion 格式")
    last_dash = partNumberVersion.rfind("-")
    part_number = partNumberVersion[:last_dash]
    version = partNumberVersion[last_dash + 1:]

    # 从 body 的 partIterationKey 取 iteration
    iteration_number = 1
    if body and body.partIterationKey:
        iteration_number = body.partIterationKey.iteration or 1

    # 查找 workspace_id
    workspace_id = _find_workspace_id(db, workspaceId)
    if not workspace_id:
        # 尝试用 UUID 解析（防止有时传 UUID）
        try:
            workspace_id = uuid.UUID(workspaceId)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"工作空间 {workspaceId!r} 不存在")

    # 判断转换是否成功（有 convertedFile 且无 errorOutput）
    succeed = bool(body and body.convertedFile and not body.errorOutput)

    # 解析包围盒
    x_min = y_min = z_min = x_max = y_max = z_max = None
    if body and body.box and len(body.box) >= 6:
        x_min, y_min, z_min, x_max, y_max, z_max = body.box[:6]

    # 解析 geometry 文件路径
    # convertedFile 是相对于 tempDir 的文件名，tempDir 是 conversions_path 下的子目录
    geometry_full_name = None
    content_length = 0

    # 优先用 convertedFileLODs（Map<Integer, String>，key=quality，value=文件名）
    lods = {}
    if body and body.convertedFileLODs:
        lods = {int(k): v for k, v in body.convertedFileLODs.items()}
    elif body and body.convertedFile:
        # 兼容：单文件模式
        lods = {0: body.convertedFile}

    from app.core.config import settings
    # 标准 vault geometry 路径格式
    vault_geo_dir = f"{workspaceId}/parts/{part_number}/{version}/{iteration_number}/geometries"

    # P3.2：收集所有 LOD 的 vault 路径和文件大小，用于批量写 Geometry 记录
    # lod_results: {quality: (geometry_full_name, content_length)}
    lod_results: dict = {}

    if lods and succeed:
        conversions_path = settings.conversions_path
        import shutil

        for quality, geo_filename in sorted(lods.items()):
            geo_filename_only = os.path.basename(geo_filename)
            geo_full_name = f"{vault_geo_dir}/{geo_filename_only}"
            vault_geo_path = os.path.join(settings.vault_path, geo_full_name)

            # 从 conversions 共享 volume 找源文件
            src_path = None
            if os.path.exists(conversions_path):
                for subdir in os.listdir(conversions_path):
                    candidate = os.path.join(conversions_path, subdir, geo_filename_only)
                    if os.path.exists(candidate):
                        src_path = candidate
                        break

            if src_path and os.path.exists(src_path):
                os.makedirs(os.path.dirname(vault_geo_path), exist_ok=True)
                shutil.copy2(src_path, vault_geo_path)
                lod_results[quality] = (geo_full_name, os.path.getsize(vault_geo_path))
            elif os.path.exists(vault_geo_path):
                lod_results[quality] = (geo_full_name, os.path.getsize(vault_geo_path))

    # 若无任何 LOD 成功，geometry_full_name 为 None（失败记录）
    if not lod_results and not succeed:
        lod_results[0] = (None, 0)

    # 以 quality=0 作为主记录（handle_conversion_callback 更新 Conversion 表状态）
    primary_quality = 0
    primary_geo, primary_len = lod_results.get(primary_quality, (None, 0))

    conversion = handle_conversion_callback(
        db=db,
        number=part_number,
        version=version,
        iteration_number=iteration_number,
        workspace_id=workspace_id,
        succeed=succeed,
        geometry_full_name=primary_geo,
        x_min=x_min, y_min=y_min, z_min=z_min,
        x_max=x_max, y_max=y_max, z_max=z_max,
        quality=primary_quality,
        content_length=primary_len,
    )

    # P3.2：为其余 LOD（quality=1, 2）追加额外 Geometry 记录
    from app.crud.conversion import add_geometry_record
    for q, (geo_name, c_len) in sorted(lod_results.items()):
        if q == primary_quality or geo_name is None:
            continue
        add_geometry_record(
            db=db,
            number=part_number,
            version=version,
            iteration_number=iteration_number,
            workspace_id=workspace_id,
            geometry_full_name=geo_name,
            x_min=x_min, y_min=y_min, z_min=z_min,
            x_max=x_max, y_max=y_max, z_max=z_max,
            quality=q,
            content_length=c_len,
        )

    return {
        "pending": conversion.pending,
        "succeed": conversion.succeed,
        "lods": len(lod_results),
        "message": "转换结果已记录（DocDoku 兼容回调）",
    }
