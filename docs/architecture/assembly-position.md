# 装配体零件位置信息机制

> **迁移来源：** `CATIA-Copilot-PLM/docs/architecture/assembly-position.md`  
> 原文记录的是 DocDoku Java EE 实现；plm-unified 已改用 FastAPI 重写，数据模型保持一致，API 路径已调整为新项目格式。

> 记录装配体 3D 展示时，零件位置/变换矩阵的存储结构、上传接口及前端渲染流程。

---

## 一、数据模型

### 1.1 核心实体：`CADInstance`

**文件：** `docdoku-plm-server/docdoku-plm-server-core/src/main/java/com/docdoku/plm/server/core/product/CADInstance.java`  
**数据库表：** `CADINSTANCE`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 主键（自增） |
| `tx` | double | X 轴平移量 |
| `ty` | double | Y 轴平移量 |
| `tz` | double | Z 轴平移量 |
| `rx` | double | X 轴旋转角（弧度，ANGLE 模式） |
| `ry` | double | Y 轴旋转角（弧度，ANGLE 模式） |
| `rz` | double | Z 轴旋转角（弧度，ANGLE 模式） |
| `rotationType` | enum | `ANGLE`（欧拉角）或 `MATRIX`（3×3旋转矩阵） |
| `m00`~`m22` | double×9 | 旋转矩阵分量（MATRIX 模式，内嵌于同一表行） |

**两种旋转模式说明：**
- `ANGLE`（默认）：用 `rx/ry/rz` 欧拉角（弧度）表示旋转，适合手动输入
- `MATRIX`：用嵌入式 `RotationMatrix`（3×3，9个 double）表示旋转，适合 CATIA/CAD 系统导出的精确矩阵

### 1.2 嵌入式旋转矩阵：`RotationMatrix`

**文件：** `docdoku-plm-server-core/.../product/RotationMatrix.java`  
`@Embeddable` 注解，直接内嵌于 `CADINSTANCE` 表，字段为 `m00, m01, m02, m10, m11, m12, m20, m21, m22`（列优先存储，构造时自动转置）。

### 1.3 关联关系：`PartUsageLink` → `CADInstance`（一对多）

**文件：** `docdoku-plm-server-core/.../product/PartUsageLink.java`  
**中间表：** `PARTUSAGELINK_CADINSTANCE`

```
PARTUSAGELINK_CADINSTANCE
  PARTUSAGELINK_ID  →  PARTUSAGELINK.ID
  CADINSTANCE_ID    →  CADINSTANCE.ID
  CADINSTANCE_ORDER   （保持实例顺序）
```

**含义：** 一个 `PartUsageLink`（装配关系，即"父零件使用子零件"）可以有**多个 `CADInstance`**，表示同一子零件在装配体中出现多次，每个实例拥有独立的位置和旋转信息。

---

## 二、上传位置信息的 API 接口

### 更新零件迭代（含装配结构和位置信息）

```
PUT /api/workspaces/{workspaceId}/parts/{partNumber}/versions/{partVersion}/iterations/{iteration}
Content-Type: application/json
Authorization: Bearer <jwt_token>
```

`components` 数组中每个子零件的 `cadInstances` 字段携带位置信息。

#### 请求体示例（ANGLE 模式 - 欧拉角）

```json
{
  "iterationNote": "更新装配位置",
  "components": [
    {
      "component": { "number": "PART-001" },
      "amount": 1,
      "unit": "",
      "optional": false,
      "referenceDescription": "",
      "comment": "",
      "cadInstances": [
        {
          "tx": 10.0,
          "ty": 0.0,
          "tz": 5.0,
          "rx": 0.0,
          "ry": 1.5707963,
          "rz": 0.0,
          "rotationType": "ANGLE"
        }
      ],
      "substitutes": []
    }
  ]
}
```

#### 请求体示例（MATRIX 模式 - 旋转矩阵）

适合从 CATIA 或其他 CAD 系统直接导出旋转矩阵的场景：

```json
{
  "components": [
    {
      "component": { "number": "PART-002" },
      "cadInstances": [
        {
          "tx": 100.0,
          "ty": 50.0,
          "tz": 0.0,
          "matrix": [1, 0, 0,
                     0, 1, 0,
                     0, 0, 1],
          "rotationType": "MATRIX"
        }
      ],
      "substitutes": []
    }
  ]
}
```

> `matrix` 为 9 个 double 的数组，行优先排列，对应 3×3 旋转矩阵。

#### 同一子零件多个实例（在不同位置各放一个）

```json
{
  "components": [
    {
      "component": { "number": "BOLT-M8" },
      "amount": 4,
      "cadInstances": [
        { "tx":  10.0, "ty": 0.0, "tz": 0.0, "rx": 0, "ry": 0, "rz": 0, "rotationType": "ANGLE" },
        { "tx": -10.0, "ty": 0.0, "tz": 0.0, "rx": 0, "ry": 0, "rz": 0, "rotationType": "ANGLE" },
        { "tx":   0.0, "ty":10.0, "tz": 0.0, "rx": 0, "ry": 0, "rz": 0, "rotationType": "ANGLE" },
        { "tx":   0.0, "ty":-10.0,"tz": 0.0, "rx": 0, "ry": 0, "rz": 0, "rotationType": "ANGLE" }
      ],
      "substitutes": []
    }
  ]
}
```

#### 服务端处理逻辑

`PartResource.java` 的 `createComponents()` 方法（约第 881~963 行）：
1. 遍历每个 `PartUsageLinkDTO` 及其 `CADInstanceDTO`
2. 通过 Dozer mapper 映射为 `CADInstance` 实体
3. 若 `rotationType == MATRIX`：调用 `cadInstance.setRotationMatrix(new RotationMatrix(dto.getMatrix()))`
4. 若 `rotationType == null`：默认设为 `RotationType.ANGLE`

---

## 三、查询装配体实例（前端 3D 渲染用）

服务端在响应时会**递归遍历整个装配树，将所有层级的变换矩阵累乘**，最终返回每个叶子零件的**全局 4×4 世界坐标矩阵**。

### 方式一：单路径 GET

```
GET /api/workspaces/{workspaceId}/products/{ciId}/instances
    ?configSpec=latest
    &path={partPath}
    &timestamp={ts}
    &diverge=false
```

### 方式二：多路径 POST

```
POST /api/workspaces/{workspaceId}/products/{ciId}/instances
Content-Type: application/json

{
  "configSpec": "latest",
  "paths": ["path1", "path2", "..."]
}
```

### 方式三：零件级别实例（快速预览）

```
GET /api/workspaces/{workspaceId}/parts/{partNumber}/versions/{partVersion}/instances
```

### 响应格式

```json
[
  {
    "id": "u1-1:u2-3",
    "partIterationId": "PART-001-A-1",
    "path": "u1-u2",
    "matrix": [
      1, 0, 0, 10.0,
      0, 1, 0,  0.0,
      0, 0, 1,  5.0,
      0, 0, 0,  1.0
    ],
    "qualities": 3,
    "xMin": -5.0, "yMin": -5.0, "zMin": -5.0,
    "xMax":  5.0, "yMax":  5.0, "zMax":  5.0,
    "files": [
      { "fullName": "api/files/workspace/part/file.obj" }
    ],
    "attributes": []
  }
]
```

> **`matrix`** 为 16 个 double 的数组，行优先排列，表示 4×4 齐次变换矩阵（全局世界坐标系）。
> 前端直接将此矩阵 `apply` 到 THREE.js mesh，无需再手动计算层级变换。

---

## 四、服务端矩阵合成机制

**文件：** `docdoku-plm-server-rest/src/main/java/com/docdoku/plm/server/rest/util/InstanceBodyWriterTools.java`

核心方法 `generateInstanceStreamWithGlobalMatrix(path, parentMatrix, ...)` 的逻辑：

```
对当前层级的每个 CADInstance：
  取平移向量 (tx, ty, tz)

  若 rotationType == ANGLE：
    combinedMatrix = parentMatrix × translate(tx,ty,tz) × rotZ(rz) × rotY(ry) × rotX(rx)

  若 rotationType == MATRIX：
    rotMat = Matrix4d(RotationMatrix.getValues(), translation, 1)
    combinedMatrix = parentMatrix × rotMat

  若当前节点是叶子（有几何体 OBJ 文件）：
    writeLeaf(combinedMatrix)    ← 输出最终 4×4 矩阵到响应流

  否则（中间装配节点）：
    递归处理子组件，传入 combinedMatrix 作为新的 parentMatrix
```

---

## 五、前端 3D 渲染流程

### 5.1 矩阵应用：`InstancesManager.js`

**文件：** `docdoku-plm-front/app/product-structure/js/dmu/InstancesManager.js`

```javascript
// 将服务端 16 元素数组转成 THREE.Matrix4（第 145~151 行）
function adaptMatrix(matrix) {
    var mat = new THREE.Matrix4();
    mat.set(
        matrix[0],  matrix[1],  matrix[2],  matrix[3],
        matrix[4],  matrix[5],  matrix[6],  matrix[7],
        matrix[8],  matrix[9],  matrix[10], matrix[11],
        matrix[12], matrix[13], matrix[14], matrix[15]
    );
    return mat;
}

// 接收实例列表，应用矩阵并计算包围盒（第 176~211 行）
function onSuccessLoadPath(instances) {
    _.each(instances, function(instance) {
        instance.matrix = adaptMatrix(instance.matrix);
        var box = new THREE.Box3(min, max).applyMatrix4(instance.matrix);
        // 发送给 Worker 排队渲染
        worker.postMessage({ fn: 'addInstance', obj: { instanceRow: instance } });
    });
}
```

### 5.2 位置编辑 UI：`cad_instance_view.js`

**文件：** `docdoku-plm-front/app/js/common-objects/views/part/cad_instance_view.js`

提供 tx/ty/tz/rx/ry/rz 六个输入框，通过 Backbone 数据绑定实时更新模型，最终随 PUT 请求一起提交。

### 5.3 新增子零件默认位置：`part_assembly_view.js`

```javascript
cadInstances: [{ tx: 0, ty: 0, tz: 0, rx: 0, ry: 0, rz: 0 }]
```

---

## 六、完整数据流

```
┌─────────────────────────────────────────┐
│  CATIA 插件 / 用户手动输入               │
│  cadInstances: [{ tx,ty,tz,rx,ry,rz }]  │
└──────────────────┬──────────────────────┘
                   │
                   ▼ PUT .../parts/{num}/versions/{ver}/iterations/{iter}
                   │   Body: { components: [{ cadInstances: [...] }] }
                   │
                   ▼ PartResource.createComponents()
                   │   → new CADInstance(tx,ty,tz,rx,ry,rz)
                   │     或 new CADInstance(RotationMatrix, tx,ty,tz)
                   │
                   ▼ 持久化到数据库
                   │   CADINSTANCE 表 + PARTUSAGELINK_CADINSTANCE 中间表
                   │
                   ▼ GET .../products/{ci}/instances?configSpec=latest&path=...
                   │
                   ▼ InstanceBodyWriterTools.generateInstanceStreamWithGlobalMatrix()
                   │   递归装配树，累乘所有层级变换矩阵
                   │   → 输出每个叶子零件的全局 4×4 矩阵（16个double）
                   │
                   ▼ 前端 InstancesManager.js
                     adaptMatrix() → THREE.Matrix4
                     mesh.applyMatrix4(matrix) → 零件出现在正确位置
```

---

## 七、关键文件速查

| 分类 | 文件路径 |
|------|----------|
| 核心实体 | `docdoku-plm-server-core/.../product/CADInstance.java` |
| 旋转矩阵 | `docdoku-plm-server-core/.../product/RotationMatrix.java` |
| 旋转类型枚举 | `docdoku-plm-server-core/.../product/RotationType.java` |
| 装配关系实体 | `docdoku-plm-server-core/.../product/PartUsageLink.java` |
| REST 接口（零件） | `docdoku-plm-server-rest/.../rest/PartResource.java` |
| REST 接口（产品） | `docdoku-plm-server-rest/.../rest/ProductResource.java` |
| DTO（位置） | `docdoku-plm-server-rest/.../dto/CADInstanceDTO.java` |
| DTO（装配关系） | `docdoku-plm-server-rest/.../dto/PartUsageLinkDTO.java` |
| 矩阵合成工具 | `docdoku-plm-server-rest/.../util/InstanceBodyWriterTools.java` |
| 前端矩阵应用 | `docdoku-plm-front/app/product-structure/js/dmu/InstancesManager.js` |
| 前端 UI 编辑 | `docdoku-plm-front/app/js/common-objects/views/part/cad_instance_view.js` |
| 前端装配视图 | `docdoku-plm-front/app/js/common-objects/views/part/part_assembly_view.js` |

---

*创建日期：2026-05-22*
