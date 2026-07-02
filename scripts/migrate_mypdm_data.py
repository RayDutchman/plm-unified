"""
myPDM → plm-unified 数据迁移脚本

用法：
    python scripts/migrate_mypdm_data.py

前置条件：
    - myPDM PostgreSQL 容器运行中 (bom_postgres, bomadmin:bompass@bom_system)
    - plm-unified PostgreSQL 可访问 (localhost:5435, plm:plmpass@plm_unified)
    - 两边的表结构已就绪
"""
import uuid
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import psycopg2
from psycopg2.extras import RealDictCursor

# ── 连接 ──────────────────────────────────────────────────
SRC = psycopg2.connect(
    host="localhost", port=5433, user="bomadmin", password="bompass", dbname="bom_system"
)
DST = psycopg2.connect(
    host="localhost", port=5435, user="plm", password="plmpass", dbname="plm_unified"
)

WS_ID = "00000000-0000-0000-0000-000000000001"

def truncate_target_tables():
    """清空目标库中待迁移的表（保留 users）"""
    cur = DST.cursor()
    cur.execute("TRUNCATE TABLE "
        "project_task_worklogs, project_task_comments, project_task_links, "
        "project_task_deps, project_tasks, project_members, projects, "
        "inventory_status_logs, inventory_review_records, inventory_document_lines, "
        "inventory_documents, inventory_stock, inventory_ledger, "
        "inventory_materials, warehouses, "
        "configuration_status_logs, configuration_review_records, "
        "configuration_working_items, configuration_profile_items, "
        "configuration_profiles, configuration_item_children, "
        "configuration_item_parts, configuration_items, "
        "eco_status_logs, eco_review_records, eco_execution_items, ecos, "
        "ecr_status_logs, ecr_review_records, ecr_affected_items, ecrs, "
        "document_group_links, document_links, document_attachments, documents, "
        "component_attachments, "
        "part_usage_links, cad_instances, "
        "part_iterations, part_revisions, part_masters, "
        "operation_logs, "
        "user_group_members, user_groups, "
        "custom_field_values, custom_field_definitions, "
        "dashboard_items, dashboard_folder_shares, dashboard_folders, user_dashboards "
        "CASCADE")
    DST.commit()
    cur.close()
    print("目标表已清空")


def s(sql, params=None):
    cur = SRC.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows
    except Exception:
        SRC.rollback()
        cur.close()
        raise


def d(sql, params=None):
    cur = DST.cursor()
    cur.execute(sql, params)
    DST.commit()
    cur.close()


def d_safe(sql, params=None):
    """执行SQL，自动回滚子事务处理错误。"""
    cur = DST.cursor()
    try:
        cur.execute(sql, params)
        DST.commit()
        return True
    except Exception:
        DST.rollback()
        return False
    finally:
        cur.close()


def d_one(sql, params=None):
    cur = DST.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    return row


# ═══════════════════════════════════════════════════════════
# Phase 1: 用户与组
# ═══════════════════════════════════════════════════════════

def migrate_users():
    """迁移用户（保持原始ID以维持FK一致性）。"""
    users = s("SELECT * FROM users")
    for u in users:
        d(
            """INSERT INTO users (id, workspace_id, username, password_hash, real_name, role, department, phone, status, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (username) DO UPDATE SET id = EXCLUDED.id""",
            (str(u["id"]), WS_ID, u["username"], u["password_hash"], u.get("real_name") or u["username"],
             u.get("role", "engineer"), u.get("department"), u.get("phone"),
             u.get("status", "active"), u.get("created_at"), u.get("updated_at"))
        )
    print(f"  users: {len(users)} 行")


def migrate_user_groups():
    """迁移用户组及成员关联，保持原始ID。"""
    groups = s("SELECT * FROM user_groups")
    for g in groups:
        d(
            """INSERT INTO user_groups (id, name, description, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING""",
            (str(g["id"]), g["name"], g.get("description"), g.get("created_at"), g.get("updated_at"))
        )
    print(f"  user_groups: {len(groups)} 行")

    members = s("SELECT * FROM user_group_members")
    count = 0
    for m in members:
        try:
            d(
                "INSERT INTO user_group_members (user_id, group_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (str(m["user_id"]), str(m["group_id"]))
            )
            count += 1
        except Exception as e:
            print(f"  skip member: {e}")
    print(f"  user_group_members: {count} 行")


# ═══════════════════════════════════════════════════════════
# Phase 2: 零件（components → part_masters + revisions + iterations）
# ═══════════════════════════════════════════════════════════

def migrate_components():
    """将 myPDM components 拆成三层。"""
    comps = s("SELECT * FROM components WHERE deleted_at IS NULL")
    # 建立映射表
    comp_to_master = {}     # component.id → part_master.id
    comp_to_revision = {}   # component.id → part_revision.id
    comp_to_iteration = {}  # component.id → part_iteration.id

    for c in comps:
        mid = str(uuid.uuid4())
        rid = str(uuid.uuid4())
        iid = str(uuid.uuid4())
        comp_to_master[str(c["id"])] = mid
        comp_to_revision[str(c["id"])] = rid
        comp_to_iteration[str(c["id"])] = iid

        # PartMaster (use admin as fallback author)
        author_id = str(c["creator_id"]) if c.get("creator_id") else "00000000-0000-0000-0000-000000000010"
        d(
            """INSERT INTO part_masters (id, workspace_id, number, name, type, standard_part, author_id, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (mid, WS_ID, c["code"], c["name"], None, False,
             author_id, c["created_at"], c["updated_at"])
        )

        # PartRevision
        status = c.get("status", "WIP")
        if status not in ("WIP", "RELEASED", "OBSOLETE"):
            status = "WIP"
        d(
            """INSERT INTO part_revisions (id, part_master_id, version, status, description, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (rid, mid, c.get("version", "A"), status, c.get("remark"), c["created_at"], c["updated_at"])
        )

        # PartIteration
        d(
            """INSERT INTO part_iterations (id, part_revision_id, iteration, check_in_date, author_id, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (iid, rid, 1, c["updated_at"] if status != "WIP" else None,
             author_id, c["created_at"], c["updated_at"])
        )

    print(f"  components → part_masters/revisions/iterations: {len(comps)} 行")

    # 跳过 component_attachments（依赖旧 components 表，暂不迁移）
    attachments = s("SELECT * FROM component_attachments")
    print(f"  component_attachments: {len(attachments)} 行 (已跳过，依赖旧components表)")

    return comp_to_master, comp_to_revision, comp_to_iteration


# ═══════════════════════════════════════════════════════════
# Phase 3: BOM（bom_items → part_usage_links）
# ═══════════════════════════════════════════════════════════

def migrate_bom(comp_to_iteration):
    """bom_items → part_usage_links。"""
    items = s("SELECT * FROM bom_items WHERE deleted_at IS NULL")
    count = 0
    for b in items:
        p_iter = comp_to_iteration.get(str(b["parent_id"]))
        c_master = comp_to_iteration.get(str(b["child_id"]))  # child_id → component → part_master via iteration
        if not p_iter:
            continue
        # child component → part_master lookup: child component.id → part_iteration → part_revision → part_master
        c_iter = comp_to_iteration.get(str(b["child_id"]))
        if not c_iter:
            continue
        # find part_master_id from iteration
        row = d_one("SELECT part_revision_id FROM part_iterations WHERE id = %s", (c_iter,))
        if not row:
            continue
        rev_row = d_one("SELECT part_master_id FROM part_revisions WHERE id = %s", (row["part_revision_id"],))
        if not rev_row:
            continue
        link_id = str(uuid.uuid4())
        d(
            """INSERT INTO part_usage_links (id, parent_iteration_id, component_master_id, amount, "order", optional)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (link_id, p_iter, rev_row["part_master_id"], b.get("quantity", 1), 0, False)
        )
        count += 1
    print(f"  bom_items → part_usage_links: {count} 行")


# ═══════════════════════════════════════════════════════════
# Phase 4: 直搬模块
# ═══════════════════════════════════════════════════════════

DIRECT_TABLES = [
    # (src_table, dst_table, columns_expr)
    ("documents", "documents",
     "id, code, name, version, status, remark, creator_id, created_at, updated_at, deleted_at"),
    ("document_attachments", "document_attachments",
     "id, file_name, file_size, file_path, file_hash, created_at, created_at as updated_at, document_id"),
    ("document_links", "document_links",
     "id, document_id, entity_type, entity_id, created_at"),
    ("document_group_links", "document_group_links",
     "document_id, group_id"),
    ("ecrs", "ecrs",
     "id, ecr_number, title, description, reason, priority, category, status, reviewers, review_mode, creator_id, document_links, cc_users, created_at, updated_at, reviewed_at, closed_at, deleted_at, eco_id"),
    ("ecr_affected_items", "ecr_affected_items",
     "id, ecr_id, entity_type, entity_id, entity_code, entity_name, entity_version, change_description, change_type, bom_impact, created_at"),
    ("ecr_review_records", "ecr_review_records",
     "id, ecr_id, reviewer_id, reviewer_name, decision, comment, created_at"),
    ("ecr_status_logs", "ecr_status_logs",
     "id, ecr_id, from_status, to_status, operator_id, operator_name, comment, created_at"),
    ("ecos", "ecos",
     "id, eco_number, ecr_id, title, description, reason, priority, category, status, reviewers, review_mode, creator_id, document_links, cc_users, release_items, frozen_entities, created_at, updated_at, reviewed_at, executed_at, closed_at, deleted_at"),
    ("eco_execution_items", "eco_execution_items",
     "id, eco_id, source, affected_item_id, entity_type, entity_id, entity_code, entity_name, entity_version, action, status, detail, new_entity_id, new_version, parent_entity_id, parent_new_entity_id, error_message, sort_order, executed_at"),
    ("eco_review_records", "eco_review_records",
     "id, eco_id, reviewer_id, reviewer_name, decision, comment, created_at"),
    ("eco_status_logs", "eco_status_logs",
     "id, eco_id, from_status, to_status, operator_id, operator_name, comment, created_at"),
    ("configuration_items", "configuration_items",
     "id, code, name, spec, remark, document_links, creator_id, created_at, updated_at, deleted_at"),
    ("configuration_item_parts", "configuration_item_parts",
     "id, configuration_item_id, part_type, part_id, is_required, quantity, sort_order, created_at"),
    ("configuration_item_children", "configuration_item_children",
     "id, parent_id, child_id, is_required, quantity, sort_order, created_at"),
    ("configuration_profiles", "configuration_profiles",
     "id, code, name, configuration_item_id, status, effectivity_start, effectivity_end, remark, creator_id, created_at, updated_at, reviewers, review_mode, cc_users, submitted_at, reviewed_at, archived_at"),
    ("configuration_profile_items", "configuration_profile_items",
     "id, profile_id, source_config_item_id, item_type, item_id, item_code, item_name, is_required, is_selected, quantity, source_type, sort_order, created_at"),
    ("configuration_working_items", "configuration_working_items",
     "id, profile_id, source_config_item_id, item_type, item_id, item_code, item_name, is_required, is_selected, quantity, source_type, sort_order, created_at"),
    ("configuration_review_records", "configuration_review_records",
     "id, profile_id, reviewer_id, reviewer_name, decision, comment, created_at"),
    ("configuration_status_logs", "configuration_status_logs",
     "id, profile_id, from_status, to_status, operator_id, operator_name, comment, created_at"),
    ("warehouses", "warehouses",
     "id, code, name, type, default_keeper_id, status, remark, created_at, updated_at, deleted_at"),
    ("inventory_materials", "inventory_materials",
     "id, code, name, spec, unit, source_type, ref_entity_type, ref_entity_id, track_mode, safety_stock, status, remark, created_at, updated_at, deleted_at"),
    ("inventory_stock", "inventory_stock",
     "id, material_id, warehouse_id, batch_no, quantity, updated_at"),
    ("inventory_ledger", "inventory_ledger",
     "id, material_id, warehouse_id, batch_no, direction, quantity, balance_after, doc_id, doc_type, doc_number, doc_line_id, operator_id, operator_name, created_at"),
    ("inventory_documents", "inventory_documents",
     "id, doc_number, doc_type, biz_type, status, warehouse_id, to_warehouse_id, reviewers, review_mode, keeper_id, keeper_name, creator_id, document_links, remark, reviewed_at, posted_at, created_at, updated_at, deleted_at"),
    ("inventory_document_lines", "inventory_document_lines",
     "id, doc_id, material_id, batch_no, quantity, direction, book_quantity, counted_quantity, remark, sort_order"),
    ("inventory_review_records", "inventory_review_records",
     "id, doc_id, reviewer_id, reviewer_name, decision, comment, created_at"),
    ("inventory_status_logs", "inventory_status_logs",
     "id, doc_id, from_status, to_status, operator_id, operator_name, comment, created_at"),
    ("projects", "projects",
     "id, code, name, owner_id, status, planned_start, planned_end, description, created_at, updated_at, deleted_at"),
    ("project_members", "project_members",
     "id, project_id, user_id, role_in_project, created_at"),
    ("project_tasks", "project_tasks",
     "id, project_id, parent_id, code, name, task_type, assignee_id, status, priority, planned_start, planned_end, actual_start, actual_end, sort_order, description, created_at, updated_at, deleted_at"),
    ("project_task_links", "project_task_links",
     "id, task_id, entity_type, entity_id, created_at"),
    ("project_task_comments", "project_task_comments",
     "id, task_id, user_id, content, created_at, updated_at, deleted_at"),
    ("project_task_deps", "project_task_deps",
     "id, project_id, predecessor_id, successor_id, dep_type, lag_days, created_at"),
    ("project_task_worklogs", "project_task_worklogs",
     "id, task_id, user_id, work_date, hours, description, created_at, updated_at"),
    ("operation_logs", "operation_logs",
     "id, user_id, username, action, target_type, target_id, detail, ip_address, created_at"),
    ("custom_field_definitions", "custom_field_definitions",
     "id, name, field_key, field_type, options, is_required, applies_to, sort_order, created_at, updated_at"),
    ("custom_field_values", "custom_field_values",
     "id, field_id, entity_type, entity_id, value_text, value_number, value_json, created_at, updated_at"),
    ("user_dashboards", "user_dashboards",
     "id, user_id, name, created_at, updated_at"),
    ("dashboard_folders", "dashboard_folders",
     "id, dashboard_id, parent_id, name, sort_order, created_at, updated_at"),
    ("dashboard_items", "dashboard_items",
     "id, folder_id, entity_type, entity_id, created_at, updated_at"),
    ("dashboard_folder_shares", "dashboard_folder_shares",
     "id, folder_id, shared_with_user_id, permission, created_at, updated_at"),
]


def migrate_direct():
    """直接复制表（结构相同）。跳过源库不存在的表。"""
    for src_tbl, dst_tbl, cols in DIRECT_TABLES:
        col_names = [c.strip() for c in cols.split(",")]
        places = ", ".join(["%s"] * len(col_names))
        try:
            rows = s(f"SELECT {cols} FROM {src_tbl}")
        except Exception:
            print(f"  {dst_tbl}: 源库无此表，跳过")
            continue
        if not rows:
            print(f"  {dst_tbl}: 0 行")
            continue
        count = 0
        for row in rows:
            vals = []
            for c in col_names:
                v = row[c] if c in row else None
                vals.append(v)
            if d_safe(f"INSERT INTO {dst_tbl} ({cols}) VALUES ({places})", vals):
                count += 1
        print(f"  {dst_tbl}: {count} 行")


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("myPDM → plm-unified 数据迁移")
    print("=" * 60)
    print()
    print("Step 1: 清空目标表...")
    truncate_target_tables()
    print()

    print("Step 2: 用户与组...")
    migrate_users()
    migrate_user_groups()
    print()

    print("Step 3: 零件（components → PartMaster/Revision/Iteration）...")
    comp_to_master, comp_to_revision, comp_to_iteration = migrate_components()
    print()

    print("Step 4: BOM（bom_items → part_usage_links）...")
    migrate_bom(comp_to_iteration)
    print()

    print("Step 5: 直搬模块...")
    migrate_direct()
    print()

    print("=" * 60)
    print("迁移完成。")
    print("=" * 60)

    SRC.close()
    DST.close()
