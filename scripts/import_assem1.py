#!/usr/bin/env python3
"""
将 DocDoku 的 Assem1 装配体（Workspace_2）导入 plm-unified。

操作：
  1. 在 plm-unified 创建 Assem1 及所有子件的 PartMaster/Revision/Iteration
  2. 写入 BOM（part_usage_links + cad_instances），使用 DocDoku 原始矩阵
  3. 把 DocDoku vault 中各子件最新 iteration 的 GLB 文件复制到 plm-unified vault
  4. 在 plm-unified DB 写入 BinaryResource + Geometry 记录（quality=0）

运行环境：WSL，plm_db 容器端口 5435，DocDoku DB 容器端口 5432
"""
from __future__ import annotations

import os
import shutil
import struct
import uuid
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import register_uuid

register_uuid()  # 让 psycopg2 自动处理 uuid.UUID 类型

# ─────────────────────────────────────────────────────────────
# 连接配置
# ─────────────────────────────────────────────────────────────
DOCDOKU_DSN = "host=localhost port=5432 dbname=docdokuplm user=changeit password=changeit"
PLM_DSN = "host=localhost port=5435 dbname=plm_unified user=plm password=plmpass"

WORKSPACE_ID_STR = "00000000-0000-0000-0000-000000000001"
WORKSPACE_NAME = "default"
WORKSPACE_ID = uuid.UUID(WORKSPACE_ID_STR)
ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")

# DocDoku vault 路径（宿主机）
# 注意：DocDoku 将零件号中的空格转为下划线存储在文件系统中
DOCDOKU_VAULT = "/home/chenweibo/CATIA-Copilot-PLM/docdoku-plm-docker/data/vault"
# plm-unified vault 路径
PLM_VAULT = "/home/chenweibo/plm-unified/vault"

DOCDOKU_WORKSPACE = "Workspace_2"
ASSEM1_NUMBER = "Assem1"
ASSEM1_ITER = 12  # 已验证的迭代版本

def utcnow():
    return datetime.now(timezone.utc)


def get_or_create_part(cur_plm, number: str, name: str) -> uuid.UUID:
    """在 plm-unified 创建 PartMaster（已存在则跳过），返回 master_id。"""
    cur_plm.execute("SELECT id FROM part_masters WHERE workspace_id=%s AND number=%s AND deleted_at IS NULL",
                    (WORKSPACE_ID, number))
    row = cur_plm.fetchone()
    if row:
        return row[0]

    master_id = uuid.uuid4()
    rev_id = uuid.uuid4()
    iter_id = uuid.uuid4()
    now = utcnow()

    cur_plm.execute("""
        INSERT INTO part_masters (id, workspace_id, number, name, standard_part, author_id, created_at, updated_at)
        VALUES (%s, %s, %s, %s, FALSE, %s, %s, %s)
        ON CONFLICT (workspace_id, number) DO NOTHING
    """, (master_id, WORKSPACE_ID, number, name, ADMIN_ID, now, now))

    cur_plm.execute("""
        INSERT INTO part_revisions (id, part_master_id, version, status, created_at, updated_at)
        VALUES (%s, %s, 'A', 'RELEASED', %s, %s)
        ON CONFLICT DO NOTHING
    """, (rev_id, master_id, now, now))

    cur_plm.execute("""
        INSERT INTO part_iterations (id, part_revision_id, iteration, author_id, check_in_date, created_at, updated_at)
        VALUES (%s, %s, 1, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (iter_id, rev_id, ADMIN_ID, now, now, now))

    return master_id


def get_iteration_id(cur_plm, number: str) -> uuid.UUID | None:
    cur_plm.execute("""
        SELECT pi.id FROM part_iterations pi
        JOIN part_revisions pr ON pr.id = pi.part_revision_id
        JOIN part_masters pm ON pm.id = pr.part_master_id
        WHERE pm.workspace_id=%s AND pm.number=%s AND pm.deleted_at IS NULL
        ORDER BY pi.iteration DESC LIMIT 1
    """, (WORKSPACE_ID, number))
    row = cur_plm.fetchone()
    return row[0] if row else None


def write_bom(cur_plm, assem1_iter_id: uuid.UUID, components: list[dict]):
    """
    写入 BOM：先清空旧数据，再批量插入 part_usage_links + cad_instances。
    components: [{number, cadInstances: [{tx,ty,tz, matrix_9}]}]
    """
    cur_plm.execute("DELETE FROM part_usage_links WHERE parent_iteration_id=%s", (assem1_iter_id,))

    for comp in components:
        child_master_id = get_component_master_id(cur_plm, comp["number"])
        if not child_master_id:
            print(f"  [WARN] 子件 {comp['number']} 未找到，跳过")
            continue

        link_id = uuid.uuid4()
        cur_plm.execute("""
            INSERT INTO part_usage_links (id, parent_iteration_id, component_master_id, amount, optional, "order")
            VALUES (%s, %s, %s, %s, FALSE, 0)
        """, (link_id, assem1_iter_id, child_master_id, comp.get("amount", 1)))

        for i, ci_data in enumerate(comp.get("cadInstances", [])):
            ci_id = uuid.uuid4()
            m = ci_data["matrix"]  # 9元素行优先
            cur_plm.execute("""
                INSERT INTO cad_instances (
                    id, usage_link_id,
                    tx, ty, tz,
                    m00, m01, m02,
                    m10, m11, m12,
                    m20, m21, m22,
                    rotation_type, "order"
                ) VALUES (%s,%s, %s,%s,%s, %s,%s,%s, %s,%s,%s, %s,%s,%s, 'MATRIX', %s)
            """, (
                ci_id, link_id,
                ci_data["tx"], ci_data["ty"], ci_data["tz"],
                m[0], m[1], m[2],
                m[3], m[4], m[5],
                m[6], m[7], m[8],
                i,
            ))


def get_component_master_id(cur_plm, number: str) -> uuid.UUID | None:
    cur_plm.execute("""
        SELECT id FROM part_masters WHERE workspace_id=%s AND number=%s AND deleted_at IS NULL
    """, (WORKSPACE_ID, number))
    row = cur_plm.fetchone()
    return row[0] if row else None


def read_glb_bbox(glb_path: str) -> tuple[float, float, float, float, float, float] | None:
    """
    从 GLB 文件的第一个 POSITION accessor 的 min/max 字段读取包围盒。
    返回 (xmin, ymin, zmin, xmax, ymax, zmax) 或 None。
    """
    try:
        import json
        with open(glb_path, "rb") as f:
            # GLB header: magic(4) + version(4) + length(4)
            magic = f.read(4)
            if magic != b"glTF":
                return None
            f.read(4)  # version
            f.read(4)  # total length
            # chunk 0: JSON
            chunk_len = struct.unpack("<I", f.read(4))[0]
            chunk_type = f.read(4)
            if chunk_type != b"JSON":
                return None
            json_data = json.loads(f.read(chunk_len))

        # 找第一个 POSITION accessor 的 min/max
        for mesh in json_data.get("meshes", []):
            for prim in mesh.get("primitives", []):
                pos_acc_idx = prim.get("attributes", {}).get("POSITION")
                if pos_acc_idx is None:
                    continue
                acc = json_data["accessors"][pos_acc_idx]
                mn = acc.get("min")
                mx = acc.get("max")
                if mn and mx and len(mn) >= 3 and len(mx) >= 3:
                    return (mn[0], mn[1], mn[2], mx[0], mx[1], mx[2])
    except Exception as e:
        print(f"  [WARN] 无法读取 GLB bbox: {e}")
    return None


def copy_geometry(number: str, src_fullname: str, cur_plm) -> str | None:
    """
    把 DocDoku vault 中的 GLB 文件复制到 plm-unified vault。
    DocDoku 在文件系统上将路径中的空格替换为下划线存储。
    """
    # DocDoku DB 里的 fullname 含空格，文件系统路径空格→下划线
    src_fs_path = os.path.join(DOCDOKU_VAULT, src_fullname.replace(" ", "_"))
    if not os.path.exists(src_fs_path):
        print(f"  [WARN] GLB 不存在: {src_fs_path}")
        return None

    # plm-unified geometry 路径格式
    glb_filename = os.path.basename(src_fullname)
    dst_fullname = f"{WORKSPACE_NAME}/parts/{number}/A/1/geometries/{glb_filename}"
    dst_path = os.path.join(PLM_VAULT, dst_fullname)
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    shutil.copy2(src_fs_path, dst_path)
    size = os.path.getsize(dst_path)

    # 从 GLB 读取 bbox
    bbox = read_glb_bbox(dst_path)
    if bbox is None:
        bbox = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    x_min, y_min, z_min, x_max, y_max, z_max = bbox

    iter_id = get_iteration_id(cur_plm, number)
    if not iter_id:
        print(f"  [WARN] iteration not found for {number}")
        return None

    now = utcnow()
    br_id = uuid.uuid4()
    cur_plm.execute("""
        INSERT INTO binary_resources (id, full_name, content_length, last_modified)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (full_name) DO UPDATE SET content_length=EXCLUDED.content_length
        RETURNING id
    """, (br_id, dst_fullname, size, now))
    br_id = cur_plm.fetchone()[0]

    # 覆盖旧 geometry 记录（quality=0）
    cur_plm.execute("DELETE FROM geometries WHERE iteration_id=%s AND quality=0", (iter_id,))
    geo_id = uuid.uuid4()
    cur_plm.execute("""
        INSERT INTO geometries (id, iteration_id, binary_resource_id, quality,
                                x_min, y_min, z_min, x_max, y_max, z_max)
        VALUES (%s, %s, %s, 0, %s, %s, %s, %s, %s, %s)
    """, (geo_id, iter_id, br_id, x_min, y_min, z_min, x_max, y_max, z_max))

    print(f"  [OK] geometry copied: {dst_fullname} ({size//1024}KB)")
    return dst_fullname


def main():
    conn_dd = psycopg2.connect(DOCDOKU_DSN)
    conn_plm = psycopg2.connect(PLM_DSN)
    cur_dd = conn_dd.cursor()
    cur_plm = conn_plm.cursor()

    print("=== 1. 读取 Assem1 子件结构 ===")
    cur_dd.execute("""
        SELECT pul.id, pul.component_partnumber, pul.amount,
               pm.name
        FROM partiteration_partusagelink ipl
        JOIN partusagelink pul ON pul.id = ipl.component_id
        JOIN partmaster pm ON pm.partnumber = pul.component_partnumber AND pm.workspace_id = %s
        WHERE ipl.workspace_id = %s
        AND ipl.partmaster_partnumber = %s
        AND ipl.partrevision_version = 'A'
        AND ipl.iteration = %s
        ORDER BY pul.id
    """, (DOCDOKU_WORKSPACE, DOCDOKU_WORKSPACE, ASSEM1_NUMBER, ASSEM1_ITER))
    usage_links = cur_dd.fetchall()
    print(f"  找到 {len(usage_links)} 条 UsageLink")

    # 按 component_partnumber 分组（同一子件可能有多个 CADInstance）
    components_map: dict[str, dict] = {}
    for link_id, comp_num, amount, comp_name in usage_links:
        if comp_num not in components_map:
            components_map[comp_num] = {
                "number": comp_num,
                "name": comp_name,
                "amount": amount,
                "link_ids": [],
                "cadInstances": [],
            }
        components_map[comp_num]["link_ids"].append(link_id)

    print("=== 2. 读取 CADInstance 矩阵 ===")
    for comp_num, comp in components_map.items():
        for link_id in comp["link_ids"]:
            cur_dd.execute("""
                SELECT ci.tx, ci.ty, ci.tz,
                       ci.m00, ci.m01, ci.m02,
                       ci.m10, ci.m11, ci.m12,
                       ci.m20, ci.m21, ci.m22
                FROM partusagelink_cadinstance pci
                JOIN cadinstance ci ON ci.id = pci.cadinstance_id
                WHERE pci.partusagelink_id = %s
            """, (link_id,))
            for row in cur_dd.fetchall():
                tx, ty, tz = row[0], row[1], row[2]
                matrix_9 = list(row[3:12])
                comp["cadInstances"].append({
                    "tx": float(tx), "ty": float(ty), "tz": float(tz),
                    "matrix": [float(v) for v in matrix_9],
                })

    print("=== 3. 查询各子件最新 GLB 文件 ===")
    # 取每个子件 iteration=7（已知有 geometry）的 GLB
    geometry_map: dict[str, str] = {}  # number -> fullname
    for comp_num in components_map:
        cur_dd.execute("""
            SELECT pig.geometry_fullname
            FROM partiteration_geometry pig
            WHERE pig.workspace_id = %s
            AND pig.partmaster_partnumber = %s
            AND pig.partrevision_version = 'A'
            AND pig.iteration = 7
            LIMIT 1
        """, (DOCDOKU_WORKSPACE, comp_num))
        row = cur_dd.fetchone()
        if row:
            geometry_map[comp_num] = row[0]
        else:
            # 降级：取最新 iteration 的任意 geometry
            cur_dd.execute("""
                SELECT pig.geometry_fullname
                FROM partiteration_geometry pig
                WHERE pig.workspace_id = %s AND pig.partmaster_partnumber = %s
                ORDER BY pig.iteration DESC LIMIT 1
            """, (DOCDOKU_WORKSPACE, comp_num))
            row = cur_dd.fetchone()
            if row:
                geometry_map[comp_num] = row[0]

    print("=== 4. 在 plm-unified 创建零件 ===")
    # 先创建 Assem1
    get_or_create_part(cur_plm, ASSEM1_NUMBER, "Assem1")
    # 创建所有子件
    for comp_num, comp in components_map.items():
        get_or_create_part(cur_plm, comp_num, comp["name"])
        print(f"  [OK] {comp_num}")
    conn_plm.commit()

    print("=== 5. 写入 BOM ===")
    assem1_iter_id = get_iteration_id(cur_plm, ASSEM1_NUMBER)
    components_list = list(components_map.values())
    write_bom(cur_plm, assem1_iter_id, components_list)
    conn_plm.commit()
    print(f"  BOM 写入完成（{len(components_list)} 个子件）")

    print("=== 6. 复制 geometry GLB 到 plm-unified vault ===")
    for comp_num, src_fullname in geometry_map.items():
        copy_geometry(comp_num, src_fullname, cur_plm)
    conn_plm.commit()

    print("\n=== 完成 ===")
    print("可以通过以下接口验证：")
    print(f"  GET http://localhost:8010/api/parts/Assem1/A/instances?workspace_id={WORKSPACE_ID_STR}")

    cur_dd.close()
    cur_plm.close()
    conn_dd.close()
    conn_plm.close()


if __name__ == "__main__":
    main()
