"""装配体 CRUD：PartIteration 更新（components + cadInstances）和矩阵合成。

2.1：write_components — 覆盖写入 part_usage_links + cad_instances
2.3：compute_instances — 递归装配树，累乘 mat4，输出全局矩阵列表

矩阵合成算法来源：DocDoku InstanceBodyWriterTools.java
  ANGLE 模式：parent × translate(tx,ty,tz) × rotZ(rz) × rotY(ry) × rotX(rx)
  MATRIX 模式：parent × Matrix4d(RotationMatrix.getValues(), translation, 1)
"""
from __future__ import annotations

import uuid
from typing import Optional

import numpy as np
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assembly import CADInstance, PartUsageLink
from app.models.binary import Geometry
from app.models.part import PartIteration, PartMaster, PartRevision
from app.schemas.assembly import (
    CADInstanceCreate,
    InstanceResponse,
    UsageLinkCreate,
)


# ---------------------------------------------------------------------------
# 2.1：PartIteration 更新（覆盖写入 components + cadInstances）
# ---------------------------------------------------------------------------

def write_components(
    db: Session,
    number: str,
    version: str,
    iteration_number: int,
    workspace_id: uuid.UUID,
    current_user_id: uuid.UUID,
    components: list[UsageLinkCreate],
    iteration_note: Optional[str] = None,
) -> PartIteration:
    """
    覆盖写入一个迭代的装配子件列表。

    规则：
      - 迭代必须存在且 check_in_date IS NULL（WIP 状态，未冻结）
      - 先删除该迭代所有旧的 part_usage_links（CASCADE 自动删 cad_instances）
      - 再逐条插入新的 usage_links + cad_instances
      - 子件编号在同一 workspace 内查找 part_masters

    对应 DocDoku PartResource.updatePartIteration() + createComponents()
    """
    # 查找迭代
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"版本 {version!r} 不存在",
        )

    iteration = (
        db.query(PartIteration)
        .filter(
            PartIteration.part_revision_id == revision.id,
            PartIteration.iteration == iteration_number,
        )
        .first()
    )
    if not iteration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"迭代 {iteration_number} 不存在",
        )

    # 必须是 WIP（未冻结）
    if iteration.check_in_date is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"迭代 {iteration_number} 已签入（冻结），无法修改",
        )

    # 必须由签出用户操作
    if revision.checkout_user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该版本未由当前用户签出，无法修改迭代内容",
        )

    # 更新备注
    if iteration_note is not None:
        iteration.iteration_note = iteration_note

    # 删除旧的 usage_links（CASCADE 自动删 cad_instances）
    db.query(PartUsageLink).filter(
        PartUsageLink.parent_iteration_id == iteration.id
    ).delete(synchronize_session=False)
    db.flush()

    # 写入新的 usage_links + cad_instances
    for comp_data in components:
        # 查找子零件 master
        component_master = (
            db.query(PartMaster)
            .filter(
                PartMaster.workspace_id == workspace_id,
                PartMaster.number == comp_data.component_number,
                PartMaster.deleted_at.is_(None),
            )
            .first()
        )
        if not component_master:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"子零件 {comp_data.component_number!r} 不存在",
            )

        usage_link = PartUsageLink(
            id=uuid.uuid4(),
            parent_iteration_id=iteration.id,
            component_master_id=component_master.id,
            amount=comp_data.amount,
            unit=comp_data.unit,
            optional=comp_data.optional,
            order=comp_data.order,
            comment=comp_data.comment,
        )
        db.add(usage_link)
        db.flush()  # 获取 usage_link.id

        # 写入 cad_instances
        for inst_data in comp_data.cad_instances:
            cad_inst = _build_cad_instance(usage_link.id, inst_data)
            db.add(cad_inst)

    db.commit()
    db.refresh(iteration)
    return iteration


def _build_cad_instance(usage_link_id: uuid.UUID, data: CADInstanceCreate) -> CADInstance:
    """把请求 schema 转换为 CADInstance ORM 对象。"""
    rotation_type = (data.rotation_type or "ANGLE").upper()
    if rotation_type not in ("ANGLE", "MATRIX"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"rotation_type 必须是 ANGLE 或 MATRIX，收到 {rotation_type!r}",
        )

    inst = CADInstance(
        id=uuid.uuid4(),
        usage_link_id=usage_link_id,
        rotation_type=rotation_type,
        tx=data.tx,
        ty=data.ty,
        tz=data.tz,
        order=data.order,
    )

    if rotation_type == "ANGLE":
        inst.rx = data.rx or 0.0
        inst.ry = data.ry or 0.0
        inst.rz = data.rz or 0.0
    else:
        # MATRIX 模式：接受行优先 9 元素数组
        # DocDoku RotationMatrix 存储为列优先（m00=values[0], m10=values[1], m20=values[2], ...）
        # 与 Java 端保持一致
        if not data.matrix or len(data.matrix) != 9:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="MATRIX 模式需要提供 9 个 double 的 matrix 数组（行优先）",
            )
        m = data.matrix
        # 输入 matrix 为行优先：m[row*3+col] = R[row][col]
        # DocDoku 字段为列优先：m{col}{row} = R[row][col]
        # 所以：m{col}{row} = m[row*3+col]
        #   第 0 列（col=0）：m00=m[0], m10=m[3], m20=m[6]
        #   第 1 列（col=1）：m01=m[1], m11=m[4], m21=m[7]
        #   第 2 列（col=2）：m02=m[2], m12=m[5], m22=m[8]
        inst.m00 = m[0]; inst.m10 = m[3]; inst.m20 = m[6]  # 第 0 列
        inst.m01 = m[1]; inst.m11 = m[4]; inst.m21 = m[7]  # 第 1 列
        inst.m02 = m[2]; inst.m12 = m[5]; inst.m22 = m[8]  # 第 2 列

    return inst


# ---------------------------------------------------------------------------
# 2.3：矩阵合成 — 递归装配树，输出全局 4×4 矩阵
# ---------------------------------------------------------------------------

def compute_instances(
    db: Session,
    root_number: str,
    root_version: str,
    workspace_id: uuid.UUID,
    config_spec: str = "latest",
) -> list[InstanceResponse]:
    """
    递归遍历装配树，层层累乘 mat4，输出每个叶子节点的全局 4×4 矩阵。

    算法来源：DocDoku InstanceBodyWriterTools.generateInstanceStreamWithGlobalMatrix()
    ANGLE：parent × translate × rotZ × rotY × rotX
    MATRIX：parent × Matrix4d(RotationMatrix.getValues(), translation, 1)

    config_spec：仅支持 "latest"（取最新签入迭代）
    """
    # 查找根节点 master
    root_master = (
        db.query(PartMaster)
        .filter(
            PartMaster.workspace_id == workspace_id,
            PartMaster.number == root_number,
            PartMaster.deleted_at.is_(None),
        )
        .first()
    )
    if not root_master:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"零件 {root_number!r} 不存在",
        )

    results: list[InstanceResponse] = []
    identity = np.eye(4, dtype=float)

    _traverse(
        db=db,
        master=root_master,
        workspace_id=workspace_id,
        parent_matrix=identity,
        path_prefix="",
        results=results,
    )
    return results


def _get_latest_checked_in_iteration(
    db: Session, master: PartMaster, workspace_id: uuid.UUID
) -> Optional[PartIteration]:
    """
    取零件的最新签入迭代（config_spec=latest）。
    优先取最新 RELEASED 版本的最新迭代，若无则取 WIP 版本的最新已签入迭代。
    """
    # 按 RELEASED > WIP 优先级取最新版本
    for status_priority in ("RELEASED", "WIP"):
        revision = (
            db.query(PartRevision)
            .filter(
                PartRevision.part_master_id == master.id,
                PartRevision.status == status_priority,
                PartRevision.deleted_at.is_(None),
            )
            .order_by(PartRevision.version.desc())
            .first()
        )
        if not revision:
            continue

        # 取该版本最新的已签入迭代（check_in_date IS NOT NULL）
        iteration = (
            db.query(PartIteration)
            .filter(
                PartIteration.part_revision_id == revision.id,
                PartIteration.check_in_date.is_not(None),
            )
            .order_by(PartIteration.iteration.desc())
            .first()
        )
        if iteration:
            return iteration

    # fallback：无已签入迭代时，取 WIP 版本的最新迭代（CATIA sync 场景）
    for status_priority in ("RELEASED", "WIP"):
        revision = (
            db.query(PartRevision)
            .filter(
                PartRevision.part_master_id == master.id,
                PartRevision.status == status_priority,
                PartRevision.deleted_at.is_(None),
            )
            .order_by(PartRevision.version.desc())
            .first()
        )
        if not revision:
            continue
        iteration = (
            db.query(PartIteration)
            .filter(PartIteration.part_revision_id == revision.id)
            .order_by(PartIteration.iteration.desc())
            .first()
        )
        if iteration:
            return iteration

    return None


def _traverse(
    db: Session,
    master: PartMaster,
    workspace_id: uuid.UUID,
    parent_matrix: np.ndarray,
    path_prefix: str,
    results: list[InstanceResponse],
) -> None:
    """
    递归遍历装配树节点。

    - 若当前节点无子件（叶子）：输出全局 mat4 到 results
    - 若有子件（装配体）：对每个 PartUsageLink + 每个 CADInstance 递归

    path_prefix：用于构造实例 ID（类似 DocDoku 的 path 字符串）
    """
    iteration = _get_latest_checked_in_iteration(db, master, workspace_id)
    if not iteration:
        # 无可用迭代，跳过（无几何数据）
        return

    # 查找该迭代的所有子件
    usage_links = (
        db.query(PartUsageLink)
        .filter(PartUsageLink.parent_iteration_id == iteration.id)
        .order_by(PartUsageLink.order)
        .all()
    )

    if not usage_links:
        # 叶子节点：输出当前的全局矩阵
        revision = db.get(PartRevision, iteration.part_revision_id)
        # 查几何文件（最高 LOD，quality=0）
        geometry = (
            db.query(Geometry)
            .filter(Geometry.iteration_id == iteration.id)
            .order_by(Geometry.quality)
            .first()
        )
        from app.models.binary import BinaryResource
        geo_full_name = None
        bbox = {}
        if geometry:
            br = db.get(BinaryResource, geometry.binary_resource_id)
            geo_full_name = br.full_name if br else None
            bbox = {
                "x_min": geometry.x_min, "y_min": geometry.y_min, "z_min": geometry.z_min,
                "x_max": geometry.x_max, "y_max": geometry.y_max, "z_max": geometry.z_max,
            }

        results.append(InstanceResponse(
            id=path_prefix or master.number,
            part_number=master.number,
            version=revision.version if revision else "?",
            iteration=iteration.iteration,
            matrix=parent_matrix.flatten(order='F').tolist(),
            geometry_full_name=geo_full_name,
            **bbox,
        ))
        return

    # 中间装配节点：遍历子件
    for link in usage_links:
        # 查子件 master
        child_master = db.get(PartMaster, link.component_master_id)
        if not child_master:
            continue

        # 查该 usage_link 的所有 CAD 实例
        cad_instances = (
            db.query(CADInstance)
            .filter(CADInstance.usage_link_id == link.id)
            .order_by(CADInstance.order)
            .all()
        )

        if not cad_instances:
            # 无位置信息：用单位矩阵（零件在原点）
            cad_instances_effective = [_identity_cad_instance()]
        else:
            cad_instances_effective = cad_instances

        for idx, cad_inst in enumerate(cad_instances_effective):
            # 计算当前实例的局部→全局矩阵
            local_mat = _cad_instance_to_matrix(cad_inst)
            combined = parent_matrix @ local_mat

            # 构造路径 ID
            child_path = f"{path_prefix}u{link.id}-{idx}"

            _traverse(
                db=db,
                master=child_master,
                workspace_id=workspace_id,
                parent_matrix=combined,
                path_prefix=child_path + ":",
                results=results,
            )


def _cad_instance_to_matrix(inst: CADInstance) -> np.ndarray:
    """
    将 CADInstance 转换为 4×4 齐次变换矩阵。

    ANGLE 模式：translate × rotZ × rotY × rotX（对应 DocDoku ANGLE 合成顺序）
    MATRIX 模式：直接用存储的 3×3 旋转矩阵 + 平移向量
    """
    mat = np.eye(4, dtype=float)

    if inst.rotation_type == "ANGLE":
        rx = inst.rx or 0.0
        ry = inst.ry or 0.0
        rz = inst.rz or 0.0

        # 各轴旋转矩阵（右手坐标系，与 DocDoku 一致）
        Rx = np.array([
            [1,        0,         0, 0],
            [0,  np.cos(rx), -np.sin(rx), 0],
            [0,  np.sin(rx),  np.cos(rx), 0],
            [0,        0,         0, 1],
        ], dtype=float)
        Ry = np.array([
            [ np.cos(ry), 0, np.sin(ry), 0],
            [          0, 1,          0, 0],
            [-np.sin(ry), 0, np.cos(ry), 0],
            [          0, 0,          0, 1],
        ], dtype=float)
        Rz = np.array([
            [np.cos(rz), -np.sin(rz), 0, 0],
            [np.sin(rz),  np.cos(rz), 0, 0],
            [         0,           0, 1, 0],
            [         0,           0, 0, 1],
        ], dtype=float)

        T = np.eye(4, dtype=float)
        T[0, 3] = inst.tx or 0.0
        T[1, 3] = inst.ty or 0.0
        T[2, 3] = inst.tz or 0.0

        # translate × rotZ × rotY × rotX（DocDoku 合成顺序）
        mat = T @ Rz @ Ry @ Rx

    else:  # MATRIX
        # DocDoku RotationMatrix 字段命名：m{col}{row}（列优先存储）
        # 即：m00=R[0][0], m10=R[1][0], m20=R[2][0]（第 0 列）
        #     m01=R[0][1], m11=R[1][1], m21=R[2][1]（第 1 列）
        #     m02=R[0][2], m12=R[1][2], m22=R[2][2]（第 2 列）
        # 填入 4×4 矩阵时：mat[row][col] = m{col}{row}
        # 列 0
        mat[0, 0] = inst.m00 or 0.0; mat[1, 0] = inst.m10 or 0.0; mat[2, 0] = inst.m20 or 0.0
        # 列 1
        mat[0, 1] = inst.m01 or 0.0; mat[1, 1] = inst.m11 or 0.0; mat[2, 1] = inst.m21 or 0.0
        # 列 2
        mat[0, 2] = inst.m02 or 0.0; mat[1, 2] = inst.m12 or 0.0; mat[2, 2] = inst.m22 or 0.0
        # 平移
        mat[0, 3] = inst.tx or 0.0
        mat[1, 3] = inst.ty or 0.0
        mat[2, 3] = inst.tz or 0.0

    return mat


class _IdentityCADInstance:
    """零位置实例的哨兵值（单位矩阵）。"""
    rotation_type = "ANGLE"
    tx = ty = tz = 0.0
    rx = ry = rz = 0.0
    m00 = m01 = m02 = m10 = m11 = m12 = m20 = m21 = m22 = None


def _identity_cad_instance() -> _IdentityCADInstance:
    return _IdentityCADInstance()
