-- =============================================================================
-- PLM Unified 核心数据库 DDL
-- 里程碑：M1.1
-- 设计参考：DocDoku PartMaster/PartRevision/PartIteration 三层模型
-- 作者：A（主写）
--
-- ⚠️  注意：此文件仅作参考文档 / 本地快速初始化之用。
--     正式环境建库请使用 Alembic：
--       cd backend && alembic upgrade head
-- =============================================================================

-- 启用 UUID 扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- 基础表：用户与工作空间（供外键引用，认证模块 B 完善）
-- =============================================================================

-- 工作空间表
-- 对应 DocDoku Workspace，每个工作空间相互隔离
CREATE TABLE IF NOT EXISTS workspaces (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ                      -- 软删除标记
);

-- 用户表（B 负责完善认证逻辑，字段体系采用 myPDM 风格）
CREATE TABLE IF NOT EXISTS users (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    username        VARCHAR(64) NOT NULL UNIQUE,  -- 登录用户名
    password_hash   VARCHAR(255) NOT NULL,
    real_name       VARCHAR(64) NOT NULL,          -- 显示名
    role            VARCHAR(32) NOT NULL,          -- 角色：admin/engineer/production/guest
    department      VARCHAR(128),
    phone           VARCHAR(32),
    status          VARCHAR(32) NOT NULL DEFAULT 'active'  -- active/disabled
        CONSTRAINT chk_users_status CHECK (status IN ('active', 'disabled')),
    workspace_id    UUID REFERENCES workspaces(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

-- =============================================================================
-- 零件主数据层
-- 对应 DocDoku PartMaster（PARTMASTER）
-- 零件的唯一标识：workspace_id + number
-- =============================================================================

CREATE TABLE IF NOT EXISTS part_masters (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id    UUID        NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
    number          VARCHAR(100) NOT NULL,        -- 零件编号（对应 DocDoku PARTNUMBER）
    name            VARCHAR(255),                 -- 零件名称
    type            VARCHAR(50),                  -- 零件类型（可选分类）
    standard_part   BOOLEAN     NOT NULL DEFAULT FALSE,  -- 是否标准件
    author_id        UUID        NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,                  -- 软删除标记

    -- 业务唯一约束：同一工作空间内零件编号不重复（软删除后可复用不在此限制）
    CONSTRAINT uq_part_masters_workspace_number UNIQUE (workspace_id, number)
);

COMMENT ON TABLE  part_masters IS '零件主数据，对应 DocDoku PartMaster';
COMMENT ON COLUMN part_masters.number        IS '零件编号，同工作空间内唯一';
COMMENT ON COLUMN part_masters.standard_part IS '是否标准件（外购/通用件）';

-- =============================================================================
-- 零件版本层
-- 对应 DocDoku PartRevision（PARTREVISION）
-- 版本标识：A, B, C…（字母递增）
-- 状态机：WIP → RELEASED → OBSOLETE
-- 注：status 使用 VARCHAR + CHECK 而非 PostgreSQL ENUM，
--     便于 Alembic 迁移中安全地增减枚举值
-- =============================================================================

CREATE TABLE IF NOT EXISTS part_revisions (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    part_master_id  UUID        NOT NULL REFERENCES part_masters(id) ON DELETE CASCADE,
    version         VARCHAR(10) NOT NULL,         -- 版本号，如 "A", "B", "AA"
    status          VARCHAR(20) NOT NULL DEFAULT 'WIP'
        CONSTRAINT chk_part_revision_status CHECK (status IN ('WIP', 'RELEASED', 'OBSOLETE')),
    description     TEXT,                         -- 版本描述（对应 DocDoku @Lob description）

    -- 签出信息（对应 DocDoku checkOutUser / checkOutDate）
    checkout_user_id UUID       REFERENCES users(id) ON DELETE RESTRICT,
    checkout_date   TIMESTAMPTZ,

    -- 状态变更记录（对应 DocDoku releaseStatusChange / obsoleteStatusChange）
    released_by_id  UUID        REFERENCES users(id) ON DELETE RESTRICT,
    released_at     TIMESTAMPTZ,
    obsoleted_by_id UUID        REFERENCES users(id) ON DELETE RESTRICT,
    obsoleted_at    TIMESTAMPTZ,

    author_id       UUID        REFERENCES users(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,                  -- 软删除标记

    -- 同一零件的版本号不重复
    CONSTRAINT uq_part_revisions_master_version UNIQUE (part_master_id, version)
);

COMMENT ON TABLE  part_revisions IS '零件版本，对应 DocDoku PartRevision';
COMMENT ON COLUMN part_revisions.version         IS '版本号，字母递增（A/B/C…）';
COMMENT ON COLUMN part_revisions.status          IS '状态机：WIP→RELEASED→OBSOLETE';
COMMENT ON COLUMN part_revisions.checkout_user_id IS '当前签出用户；NULL 表示未签出';
COMMENT ON COLUMN part_revisions.checkout_date   IS '签出时间，与 checkout_user_id 同步写入';

-- =============================================================================
-- 零件迭代层
-- 对应 DocDoku PartIteration（PARTITERATION）
-- 迭代编号：1, 2, 3…（整数递增）
-- =============================================================================

CREATE TABLE IF NOT EXISTS part_iterations (
    id               UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    part_revision_id UUID        NOT NULL REFERENCES part_revisions(id) ON DELETE CASCADE,
    iteration        INTEGER     NOT NULL CHECK (iteration > 0),  -- 迭代号，从 1 开始

    -- 迭代备注（对应 DocDoku iterationNote）
    iteration_note   TEXT,

    -- 原生 CAD 文件引用（对应 DocDoku nativeCADFile → BinaryResource）
    -- 存储 binary_resources 表的 id
    native_cad_file_id UUID,                      -- FK 见下方 binary_resources 表创建后添加

    author_id       UUID        NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- 签入时间（对应 DocDoku checkInDate，签入后置为当前时间，WIP 时为 NULL）
    check_in_date    TIMESTAMPTZ,

    -- 同一版本内迭代号不重复
    CONSTRAINT uq_part_iterations_revision_iteration UNIQUE (part_revision_id, iteration)
);

COMMENT ON TABLE  part_iterations IS '零件迭代，对应 DocDoku PartIteration';
COMMENT ON COLUMN part_iterations.iteration       IS '迭代号，同版本内从 1 递增';
COMMENT ON COLUMN part_iterations.check_in_date  IS '签入时间；NULL 表示当前迭代仍在 WIP';
COMMENT ON COLUMN part_iterations.native_cad_file_id IS '原生 CAD 文件，指向 binary_resources';

-- =============================================================================
-- 二进制资源表
-- 对应 DocDoku BinaryResource（含 Geometry 父类）
-- fullName 路径格式：{workspace}/{parts}/{number}/{version}/{iteration}/nativecad/{filename}
--   或几何文件：{workspace}/{parts}/{number}/{version}/{iteration}/geometries/{filename}
-- =============================================================================

CREATE TABLE IF NOT EXISTS binary_resources (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- 完整路径，全局唯一，即 vault 存储键（对应 DocDoku BinaryResource.fullName）
    full_name       VARCHAR(500) NOT NULL UNIQUE,
    content_length  BIGINT      NOT NULL DEFAULT 0,   -- 文件大小（字节）
    last_modified   TIMESTAMPTZ NOT NULL DEFAULT NOW() -- 最后修改时间
);

COMMENT ON TABLE  binary_resources IS '二进制文件元数据，对应 DocDoku BinaryResource';
COMMENT ON COLUMN binary_resources.full_name IS 'vault 路径键，格式：{ws}/parts/{num}/{ver}/{iter}/nativecad/{file}';

-- 补全 part_iterations 的 native_cad_file_id 外键（binary_resources 已创建）
ALTER TABLE part_iterations
    ADD CONSTRAINT fk_part_iterations_native_cad
    FOREIGN KEY (native_cad_file_id) REFERENCES binary_resources(id) ON DELETE SET NULL;

-- =============================================================================
-- 几何体表
-- 对应 DocDoku Geometry（继承自 BinaryResource）
-- 每个迭代可有多个几何体（不同 LOD/质量级别）
-- =============================================================================

CREATE TABLE IF NOT EXISTS geometries (
    id           UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    iteration_id UUID    NOT NULL REFERENCES part_iterations(id) ON DELETE CASCADE,

    -- 关联的 binary_resource（存储实际文件元数据）
    binary_resource_id UUID NOT NULL REFERENCES binary_resources(id) ON DELETE CASCADE,

    -- 质量等级（对应 DocDoku Geometry.quality，0=最高，值越大越低）
    quality      INTEGER NOT NULL DEFAULT 0 CHECK (quality >= 0),

    -- 包围盒（轴对齐 AABB，单位毫米，几何体必须有包围盒）
    x_min        DOUBLE PRECISION NOT NULL,
    y_min        DOUBLE PRECISION NOT NULL,
    z_min        DOUBLE PRECISION NOT NULL,
    x_max        DOUBLE PRECISION NOT NULL,
    y_max        DOUBLE PRECISION NOT NULL,
    z_max        DOUBLE PRECISION NOT NULL
);

COMMENT ON TABLE  geometries IS '几何体 LOD 层级，对应 DocDoku Geometry';
COMMENT ON COLUMN geometries.quality IS 'LOD 质量等级，0=最高精度，数值越大越低';
COMMENT ON COLUMN geometries.x_min   IS '包围盒 X 轴最小值（毫米）';
COMMENT ON COLUMN geometries.x_max   IS '包围盒 X 轴最大值（毫米）';

-- =============================================================================
-- 零件使用关系表（装配体 BOM）
-- 对应 DocDoku PartUsageLink（PARTUSAGELINK）
-- 表达"父迭代 → 子零件主数据"的装配引用关系
-- =============================================================================

CREATE TABLE IF NOT EXISTS part_usage_links (
    id                   UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- 父零件的迭代（对应 PARTITERATION_PARTUSAGELINK 中间表关联的父迭代）
    parent_iteration_id  UUID    NOT NULL REFERENCES part_iterations(id) ON DELETE CASCADE,
    -- 子零件的主数据（对应 DocDoku PartUsageLink.component → PartMaster）
    component_master_id  UUID    NOT NULL REFERENCES part_masters(id) ON DELETE RESTRICT,

    -- 用量信息（对应 DocDoku amount / unit）
    amount               DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    unit                 VARCHAR(20),              -- 单位，如 "ea"、"mm"

    -- 可选件标记（对应 DocDoku PartUsageLink.optional）
    optional             BOOLEAN  NOT NULL DEFAULT FALSE,
    -- 在父装配体中的排列顺序（对应 COMPONENT_ORDER）
    "order"              INTEGER  NOT NULL DEFAULT 0,

    comment              TEXT,                     -- 备注（对应 DocDoku commentData）
    reference_description TEXT,                   -- 参考描述

    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  part_usage_links IS '装配 BOM 使用关系，对应 DocDoku PartUsageLink';
COMMENT ON COLUMN part_usage_links.parent_iteration_id IS '父装配体迭代';
COMMENT ON COLUMN part_usage_links.component_master_id IS '子零件主数据（引用 part_masters）';
COMMENT ON COLUMN part_usage_links.optional            IS '是否为可选件';
COMMENT ON COLUMN part_usage_links."order"             IS '在父装配体中的子件排序';

-- =============================================================================
-- CAD 实例表（装配位置/变换矩阵）
-- 对应 DocDoku CADInstance（CADINSTANCE）
-- 一个 PartUsageLink 可以有多个 CADInstance（同一子件多次出现）
-- 注：rotation_type 使用 VARCHAR + CHECK 而非 PostgreSQL ENUM
-- =============================================================================

CREATE TABLE IF NOT EXISTS cad_instances (
    id             UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    usage_link_id  UUID    NOT NULL REFERENCES part_usage_links(id) ON DELETE CASCADE,

    -- 平移向量（单位：毫米，对应 DocDoku CADInstance.tx/ty/tz）
    tx  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    ty  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    tz  DOUBLE PRECISION NOT NULL DEFAULT 0.0,

    -- 旋转类型（ANGLE=欧拉角，MATRIX=旋转矩阵）
    rotation_type  VARCHAR(10) NOT NULL DEFAULT 'ANGLE'
        CONSTRAINT chk_cad_instance_rotation_type CHECK (rotation_type IN ('ANGLE', 'MATRIX')),

    -- ANGLE 模式：欧拉角（弧度，对应 DocDoku CADInstance.rx/ry/rz）
    rx  DOUBLE PRECISION,
    ry  DOUBLE PRECISION,
    rz  DOUBLE PRECISION,

    -- MATRIX 模式：3×3 旋转矩阵（列优先存储，对应 DocDoku RotationMatrix）
    -- 命名沿用 DocDoku 约定：m{行}{列}
    m00 DOUBLE PRECISION, m01 DOUBLE PRECISION, m02 DOUBLE PRECISION,
    m10 DOUBLE PRECISION, m11 DOUBLE PRECISION, m12 DOUBLE PRECISION,
    m20 DOUBLE PRECISION, m21 DOUBLE PRECISION, m22 DOUBLE PRECISION,

    -- 在 usage_link 中的排序（对应 CADINSTANCE_ORDER）
    "order"  INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT chk_cad_instances_angle  CHECK (
        rotation_type != 'ANGLE'  OR (rx IS NOT NULL AND ry IS NOT NULL AND rz IS NOT NULL)
    ),
    CONSTRAINT chk_cad_instances_matrix CHECK (
        rotation_type != 'MATRIX' OR (
            m00 IS NOT NULL AND m01 IS NOT NULL AND m02 IS NOT NULL AND
            m10 IS NOT NULL AND m11 IS NOT NULL AND m12 IS NOT NULL AND
            m20 IS NOT NULL AND m21 IS NOT NULL AND m22 IS NOT NULL
        )
    )
);

COMMENT ON TABLE  cad_instances IS '零件在装配体中的位置/变换，对应 DocDoku CADInstance';
COMMENT ON COLUMN cad_instances.rotation_type IS 'ANGLE=欧拉角(弧度)，MATRIX=3×3旋转矩阵';
COMMENT ON COLUMN cad_instances.tx  IS 'X 轴平移量（毫米）';
COMMENT ON COLUMN cad_instances.ty  IS 'Y 轴平移量（毫米）';
COMMENT ON COLUMN cad_instances.tz  IS 'Z 轴平移量（毫米）';
COMMENT ON COLUMN cad_instances.rx  IS 'ANGLE 模式：X 轴旋转角（弧度）';
COMMENT ON COLUMN cad_instances.m00 IS 'MATRIX 模式：旋转矩阵第0行第0列（列优先存储，与 DocDoku RotationMatrix 一致）';

-- =============================================================================
-- 索引（查询优化）
-- =============================================================================

-- part_masters：按工作空间列表查询
CREATE INDEX idx_part_masters_workspace   ON part_masters  (workspace_id) WHERE deleted_at IS NULL;
-- part_masters：按编号模糊搜索
CREATE INDEX idx_part_masters_number      ON part_masters  (workspace_id, number) WHERE deleted_at IS NULL;

-- part_revisions：按零件查所有版本
CREATE INDEX idx_part_revisions_master    ON part_revisions (part_master_id) WHERE deleted_at IS NULL;
-- part_revisions：已签出列表（供并发检查）
CREATE INDEX idx_part_revisions_checkout  ON part_revisions (checkout_user_id) WHERE checkout_user_id IS NOT NULL;
-- part_revisions：状态筛选
CREATE INDEX idx_part_revisions_status    ON part_revisions (status) WHERE deleted_at IS NULL;

-- part_iterations：按版本查所有迭代
CREATE INDEX idx_part_iterations_revision ON part_iterations (part_revision_id);

-- geometries：按迭代查几何体
CREATE INDEX idx_geometries_iteration     ON geometries (iteration_id);

-- part_usage_links：按父迭代查 BOM
CREATE INDEX idx_part_usage_links_parent  ON part_usage_links (parent_iteration_id);
-- part_usage_links：按子零件反查被哪些装配体使用（Where-Used）
CREATE INDEX idx_part_usage_links_component ON part_usage_links (component_master_id);

-- cad_instances：按 usage_link 查所有实例
CREATE INDEX idx_cad_instances_usage_link ON cad_instances (usage_link_id);

-- binary_resources：路径前缀查询（vault 文件管理）
CREATE INDEX idx_binary_resources_fullname ON binary_resources (full_name varchar_pattern_ops);

-- =============================================================================
-- updated_at 自动更新触发器（通用函数）
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为含 updated_at 字段的表挂载触发器
CREATE TRIGGER trg_workspaces_updated_at
    BEFORE UPDATE ON workspaces
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_part_masters_updated_at
    BEFORE UPDATE ON part_masters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_part_revisions_updated_at
    BEFORE UPDATE ON part_revisions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
