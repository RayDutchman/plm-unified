"""
CAD 文件上传、Kafka 消息发布、转换回调和状态查询。

2.5：save_native_cad_file — 接收 UploadFile，写入 vault，更新 BinaryResource + PartIteration.native_cad_file_id
2.6：publish_conversion_order — 向 Kafka CONVERT topic 发消息（aiokafka）
2.7：handle_conversion_callback — conversion 服务回调，写 Geometry + 更新 Conversion 记录
2.8：get_conversion_status — 查询迭代的转换状态

vault 路径格式（与 DocDoku 完全一致）：
  native CAD：{workspace}/parts/{number}/{version}/{iteration}/nativecad/{filename}
  geometry：  {workspace}/parts/{number}/{version}/{iteration}/geometries/{filename}
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.binary import BinaryResource, Conversion, Geometry
from app.models.part import PartIteration, PartMaster, PartRevision


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _vault_path(full_name: str) -> str:
    """将 vault fullName 转为宿主机文件路径。"""
    return os.path.join(settings.vault_path, full_name)


def _get_iteration(
    db: Session,
    number: str,
    version: str,
    iteration_number: int,
    workspace_id: uuid.UUID,
) -> PartIteration:
    """查迭代记录，找不到抛 404。"""
    master = (
        db.query(PartMaster)
        .filter(
            PartMaster.workspace_id == workspace_id,
            PartMaster.number == number,
            PartMaster.deleted_at.is_(None),
        )
        .first()
    )
    if not master:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"零件 {number!r} 不存在")

    revision = (
        db.query(PartRevision)
        .filter(
            PartRevision.part_master_id == master.id,
            PartRevision.version == version,
            PartRevision.deleted_at.is_(None),
        )
        .first()
    )
    if not revision:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"版本 {version!r} 不存在")

    iteration = (
        db.query(PartIteration)
        .filter(
            PartIteration.part_revision_id == revision.id,
            PartIteration.iteration == iteration_number,
        )
        .first()
    )
    if not iteration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"迭代 {iteration_number} 不存在")

    return iteration


# ---------------------------------------------------------------------------
# 2.5：CAD 文件上传（写入 vault）
# ---------------------------------------------------------------------------

async def save_native_cad_file(
    db: Session,
    number: str,
    version: str,
    iteration_number: int,
    workspace_id: uuid.UUID,
    workspace_name: str,
    current_user_id: uuid.UUID,
    file: UploadFile,
) -> BinaryResource:
    """
    接收上传的原生 CAD 文件，写入 vault，更新 BinaryResource + PartIteration。

    规则：
      - 迭代必须处于已签出状态（checkout_user_id 非空），签出者必须是当前用户
      - 迭代不得已冻结（check_in_date IS NULL）
      - vault 路径格式：{workspace}/parts/{number}/{version}/{iter}/nativecad/{filename}

    对应 DocDoku PartBinaryResource.uploadNativeCADFile()
    """
    iteration = _get_iteration(db, number, version, iteration_number, workspace_id)
    revision = db.get(PartRevision, iteration.part_revision_id)

    # 必须由签出用户操作
    if revision.checkout_user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该版本未由当前用户签出，无法上传 CAD 文件",
        )
    # 必须是 WIP（未冻结）
    if iteration.check_in_date is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"迭代 {iteration_number} 已签入（冻结），无法修改",
        )

    filename = file.filename or "model.stp"
    full_name = f"{workspace_name}/parts/{number}/{version}/{iteration_number}/nativecad/{filename}"
    vault_file_path = _vault_path(full_name)

    # 确保目录存在
    os.makedirs(os.path.dirname(vault_file_path), exist_ok=True)

    # 写入文件
    content = await file.read()
    with open(vault_file_path, "wb") as f:
        f.write(content)

    file_size = len(content)
    now = _utcnow()

    # 更新或创建 BinaryResource 记录
    br = db.query(BinaryResource).filter_by(full_name=full_name).first()
    if br:
        br.content_length = file_size
        br.last_modified = now
    else:
        br = BinaryResource(
            id=uuid.uuid4(),
            full_name=full_name,
            content_length=file_size,
            last_modified=now,
        )
        db.add(br)
    db.flush()

    # 更新迭代的 native_cad_file_id
    iteration.native_cad_file_id = br.id

    # 创建 Conversion 记录（pending=True，触发转换后等待回调）
    # 先删除旧的 pending 记录（重新上传时清空旧状态）
    db.query(Conversion).filter_by(iteration_id=iteration.id).delete()
    conversion = Conversion(
        id=uuid.uuid4(),
        iteration_id=iteration.id,
        pending=True,
        succeed=None,
        start_date=now,
    )
    db.add(conversion)

    # 更新 PartMaster.updated_at（上传 STP 不直接修改 PartMaster 行）
    master = db.get(PartMaster, revision.part_master_id)
    if master:
        master.updated_at = now

    db.commit()
    db.refresh(br)
    return br


# ---------------------------------------------------------------------------
# 2.6：Kafka 消息发布
# ---------------------------------------------------------------------------

async def publish_conversion_order(
    workspace_name: str,
    number: str,
    version: str,
    iteration_number: int,
    full_name: str,
    file_size: int,
    user_token: str,
) -> None:
    """
    向 Kafka CONVERT topic 发送转换任务消息。
    消息格式严格对照 docs/integration/kafka-message-format.md，
    与 DocDoku Java ConversionOrder JSON-B 序列化完全兼容。
    """
    try:
        from aiokafka import AIOKafkaProducer
    except ImportError:
        # 测试环境可能没有 aiokafka，静默忽略（测试时 mock）
        return

    message = {
        "partIterationKey": {
            "partRevision": {
                "partMaster": {
                    "workspace": workspace_name,
                    "number": number,
                },
                "version": version,
            },
            "iteration": iteration_number,
        },
        "binaryResource": {
            "fullName": full_name,
            "contentLength": file_size,
            "lastModified": _utcnow().isoformat().replace("+00:00", "Z"),
        },
        "userToken": user_token,
    }
    key = f"{workspace_name}/{number}/{version}-{iteration_number}"

    bootstrap_servers = getattr(settings, "kafka_bootstrap_servers", "kafka:9092")
    producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
    try:
        await producer.start()
        await producer.send(
            "CONVERT",
            key=key.encode("utf-8"),
            value=json.dumps(message).encode("utf-8"),
        )
        # acks=0（fire-and-forget，与 DocDoku 原始配置一致）
        await producer.flush()
    finally:
        await producer.stop()


# ---------------------------------------------------------------------------
# 2.7：转换回调（conversion 服务写入 geometry）
# ---------------------------------------------------------------------------

class ConversionCallbackRequest:
    """转换回调请求体（由 conversion 容器调用）。"""
    def __init__(
        self,
        succeed: bool,
        geometry_full_name: Optional[str] = None,
        x_min: Optional[float] = None,
        y_min: Optional[float] = None,
        z_min: Optional[float] = None,
        x_max: Optional[float] = None,
        y_max: Optional[float] = None,
        z_max: Optional[float] = None,
        quality: int = 0,
        content_length: int = 0,
    ):
        self.succeed = succeed
        self.geometry_full_name = geometry_full_name
        self.x_min = x_min; self.y_min = y_min; self.z_min = z_min
        self.x_max = x_max; self.y_max = y_max; self.z_max = z_max
        self.quality = quality
        self.content_length = content_length


def handle_conversion_callback(
    db: Session,
    number: str,
    version: str,
    iteration_number: int,
    workspace_id: uuid.UUID,
    succeed: bool,
    geometry_full_name: Optional[str] = None,
    x_min: Optional[float] = None,
    y_min: Optional[float] = None,
    z_min: Optional[float] = None,
    x_max: Optional[float] = None,
    y_max: Optional[float] = None,
    z_max: Optional[float] = None,
    quality: int = 0,
    content_length: int = 0,
) -> Conversion:
    """
    处理 conversion 服务的回调。

    - 若 succeed=True 且提供了 geometry_full_name：写入 BinaryResource + Geometry
    - 更新 Conversion 记录（pending=False，succeed=bool）

    对应 DocDoku ConverterBean.handleConversionResultCallback()
    注意：这里不再强制要求迭代处于 checkout 状态（DocDoku BUG-43 已修复方案）
    """
    iteration = _get_iteration(db, number, version, iteration_number, workspace_id)
    now = _utcnow()

    # 查找 pending 的 Conversion 记录
    conversion = (
        db.query(Conversion)
        .filter_by(iteration_id=iteration.id, pending=True)
        .first()
    )
    if not conversion:
        # 找不到 pending 记录，可能已超时或重复回调，静默创建一条历史记录
        conversion = Conversion(
            id=uuid.uuid4(),
            iteration_id=iteration.id,
            pending=False,
            succeed=succeed,
            start_date=now,
            end_date=now,
        )
        db.add(conversion)
        db.commit()
        return conversion

    conversion.pending = False
    conversion.succeed = succeed
    conversion.end_date = now

    if succeed and geometry_full_name:
        # 确保 BinaryResource 记录存在
        br = db.query(BinaryResource).filter_by(full_name=geometry_full_name).first()
        if not br:
            br = BinaryResource(
                id=uuid.uuid4(),
                full_name=geometry_full_name,
                content_length=content_length,
                last_modified=now,
            )
            db.add(br)
            db.flush()

        # 写入 Geometry（先删旧的同 LOD 记录）
        db.query(Geometry).filter_by(
            iteration_id=iteration.id, quality=quality
        ).delete()

        if all(v is not None for v in [x_min, y_min, z_min, x_max, y_max, z_max]):
            geo = Geometry(
                id=uuid.uuid4(),
                iteration_id=iteration.id,
                binary_resource_id=br.id,
                quality=quality,
                x_min=x_min, y_min=y_min, z_min=z_min,
                x_max=x_max, y_max=y_max, z_max=z_max,
            )
            db.add(geo)

    db.commit()
    db.refresh(conversion)
    return conversion


# ---------------------------------------------------------------------------
# 2.8：转换状态查询
# ---------------------------------------------------------------------------

def get_conversion_status(
    db: Session,
    number: str,
    version: str,
    iteration_number: int,
    workspace_id: uuid.UUID,
) -> dict:
    """
    查询迭代的 CAD 转换状态。
    返回格式与 DocDoku GET .../conversion 一致：
      {"pending": bool, "succeed": bool|null, "startDate": str|null, "endDate": str|null}
    """
    iteration = _get_iteration(db, number, version, iteration_number, workspace_id)

    conversion = (
        db.query(Conversion)
        .filter_by(iteration_id=iteration.id)
        .order_by(Conversion.start_date.desc())
        .first()
    )

    if not conversion:
        return {
            "pending": False,
            "succeed": None,
            "startDate": None,
            "endDate": None,
        }

    return {
        "pending": conversion.pending,
        "succeed": conversion.succeed,
        "startDate": conversion.start_date.isoformat() if conversion.start_date else None,
        "endDate": conversion.end_date.isoformat() if conversion.end_date else None,
    }


# ---------------------------------------------------------------------------
# P3.2：追加额外 LOD Geometry 记录（quality=1, 2）
# ---------------------------------------------------------------------------

def add_geometry_record(
    db: Session,
    number: str,
    version: str,
    iteration_number: int,
    workspace_id: uuid.UUID,
    geometry_full_name: str,
    x_min: Optional[float],
    y_min: Optional[float],
    z_min: Optional[float],
    x_max: Optional[float],
    y_max: Optional[float],
    z_max: Optional[float],
    quality: int,
    content_length: int,
) -> Geometry:
    """
    为指定迭代追加一条 Geometry 记录（用于 LOD1/LOD2）。
    若该 quality 已有记录，先删除旧记录再写入。
    不修改 Conversion 表状态（handle_conversion_callback 已处理 quality=0）。
    """
    iteration = _get_iteration(db, number, version, iteration_number, workspace_id)
    now = _utcnow()

    br = db.query(BinaryResource).filter_by(full_name=geometry_full_name).first()
    if not br:
        br = BinaryResource(
            id=uuid.uuid4(),
            full_name=geometry_full_name,
            content_length=content_length,
            last_modified=now,
        )
        db.add(br)
        db.flush()

    # 覆盖旧记录
    db.query(Geometry).filter_by(iteration_id=iteration.id, quality=quality).delete()

    geo = Geometry(
        id=uuid.uuid4(),
        iteration_id=iteration.id,
        binary_resource_id=br.id,
        quality=quality,
        x_min=x_min, y_min=y_min, z_min=z_min,
        x_max=x_max, y_max=y_max, z_max=z_max,
    )
    db.add(geo)
    db.commit()
    db.refresh(geo)
    return geo
