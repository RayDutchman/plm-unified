# REST API 参考

> **本文档分两部分：**
> - **Part 1（本页顶部）**：plm-unified FastAPI 新接口（M1 实现，持续更新）
> - **Part 2（本页底部）**：DocDoku 原始接口笔记（迁移自 CATIA-Copilot-PLM，保留作参考）

---

## Part 1：plm-unified 新接口（M1）

> 本地 Swagger UI：`http://localhost:8010/api/docs`  
> 认证：除 `/api/auth/token` 外，所有端点需要 `Authorization: Bearer <access_token>`

### 通用约定

| 项 | 说明 |
|---|---|
| 基础路径 | `http://localhost:8010` |
| Content-Type | `application/json`（除登录接口用 form-data） |
| 响应字段格式 | camelCase（`checkoutUserId` 而非 `checkout_user_id`） |
| 请求体字段格式 | camelCase 或 snake_case 均可（`populate_by_name=True`） |
| 错误格式 | `{"detail": "错误描述"}` |
| 软删除 | 已删除记录不出现在任何列表和查询中 |

---

### 认证（Auth）

#### POST `/api/auth/token` — 登录获取令牌

请求体（`application/x-www-form-urlencoded`）：

```
username=admin&password=admin12345
```

响应（200）：

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

- `access_token` 有效期 8 小时（`typ=access`）
- `refresh_token` 有效期 7 天（`typ=refresh`），仅用于刷新，不可直接访问业务接口

| 状态码 | 原因 |
|---|---|
| 200 | 登录成功 |
| 401 | 用户名或密码错误 |

---

#### POST `/api/auth/refresh` — 刷新令牌

请求体（JSON）：

```json
{ "refreshToken": "eyJ..." }
```

响应（200）：同 `/token`，返回新的 access + refresh 令牌对。

| 状态码 | 原因 |
|---|---|
| 200 | 刷新成功 |
| 401 | refresh_token 无效/过期/类型错误 |

---

#### GET `/api/auth/me` — 当前用户信息

响应（200）：

```json
{
  "id": "00000000-0000-0000-0000-000000000010",
  "workspaceId": "00000000-0000-0000-0000-000000000001",
  "username": "admin",
  "realName": "系统管理员",
  "role": "admin",
  "department": null,
  "phone": null,
  "status": "active",
  "createdAt": "2026-06-29T00:00:00Z",
  "updatedAt": "2026-06-29T00:00:00Z"
}
```

---

#### POST `/api/auth/change-password` — 修改密码

请求体（JSON）：

```json
{ "oldPassword": "admin12345", "newPassword": "newpass123" }
```

响应（200）：`{"message": "密码修改成功"}`

| 状态码 | 原因 |
|---|---|
| 200 | 修改成功 |
| 400 | 原密码错误 |
| 401 | 未登录 |

---

### 零件管理（Parts）

所有零件接口均需 `workspace_id` 参数（query 或 body），用于隔离工作空间数据。

#### POST `/api/parts` — 创建零件

**原子操作**：一次请求创建三层数据（PartMaster + PartRevision A + PartIteration 1），并自动以创建者身份签出。

请求体（JSON）：

```json
{
  "number": "PART-001",
  "name": "主轴零件",
  "workspaceId": "00000000-0000-0000-0000-000000000001",
  "type": "机械件",
  "standardPart": false,
  "description": "首版描述（可选）"
}
```

字段约束：

| 字段 | 类型 | 约束 |
|---|---|---|
| `number` | string | 必填，1~100 字符，工作空间内唯一 |
| `name` | string | 必填，1~255 字符 |
| `workspaceId` | UUID | 必填 |
| `type` | string | 可选，max 50 字符 |
| `standardPart` | bool | 默认 false |
| `description` | string | 可选，传给首个版本 |

响应（201）：

```json
{
  "id": "uuid",
  "workspaceId": "uuid",
  "number": "PART-001",
  "name": "主轴零件",
  "type": "机械件",
  "standardPart": false,
  "authorId": "uuid",
  "createdAt": "2026-06-29T...",
  "updatedAt": "2026-06-29T...",
  "deletedAt": null,
  "revisions": [
    {
      "id": "uuid",
      "version": "A",
      "status": "WIP",
      "description": "首版描述",
      "checkoutUserId": "uuid",
      "checkoutDate": "2026-06-29T...",
      "createdAt": "2026-06-29T...",
      "iterations": [
        {
          "id": "uuid",
          "iteration": 1,
          "iterationNote": null,
          "nativeCadFileId": null,
          "checkInDate": null,
          "authorId": "uuid",
          "createdAt": "2026-06-29T..."
        }
      ]
    }
  ]
}
```

| 状态码 | 原因 |
|---|---|
| 201 | 创建成功 |
| 409 | 同工作空间编号已存在 |
| 401 | 未登录 |

---

#### GET `/api/parts` — 零件列表

Query 参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `workspace_id` | UUID | ✅ | 工作空间 ID |
| `skip` | int | - | 分页偏移，默认 0 |
| `limit` | int | - | 每页条数，默认 50，最大 200 |

响应（200）：`PartListItem[]`，每项含最新版本签出状态：

```json
[
  {
    "id": "uuid",
    "workspaceId": "uuid",
    "number": "PART-001",
    "name": "主轴零件",
    "type": "机械件",
    "standardPart": false,
    "authorId": "uuid",
    "createdAt": "...",
    "updatedAt": "...",
    "latestVersion": "A",
    "latestStatus": "WIP",
    "checkoutUserId": "uuid"
  }
]
```

---

#### GET `/api/parts/{number}` — 查询单个零件

Query 参数：`workspace_id`（必填）

响应（200）：同 `POST /api/parts` 的 `PartResponse`，含完整版本/迭代层级。

| 状态码 | 原因 |
|---|---|
| 200 | 返回零件详情 |
| 404 | 零件不存在或已删除 |

---

#### PUT `/api/parts/{number}/{version}/checkout` — 签出

Query 参数：`workspace_id`（必填）

**行为**：对 `part_revisions` 行加 `SELECT FOR UPDATE`，原子检查并设置签出锁。

响应（200）：

```json
{
  "number": "PART-001",
  "version": "A",
  "status": "WIP",
  "checkoutUserId": "uuid",
  "checkoutDate": "2026-06-29T...",
  "message": "签出成功"
}
```

| 状态码 | 原因 |
|---|---|
| 200 | 签出成功 |
| 409 | 已被其他用户签出 |
| 409 | 版本不是 WIP 状态（RELEASED/OBSOLETE 不可签出） |
| 404 | 零件或版本不存在 |

---

#### PUT `/api/parts/{number}/{version}/checkin` — 签入

Query 参数：`workspace_id`（必填），`iteration_note`（可选备注）

**行为**：
1. 冻结当前草稿迭代（写 `checkInDate`）
2. 创建下一迭代（`iteration + 1`，`checkInDate = null`）
3. 清除签出锁（`checkoutUserId = null`）

响应（200）：`CheckoutResponse`，`checkoutUserId` 为 null。

| 状态码 | 原因 |
|---|---|
| 200 | 签入成功 |
| 409 | 未签出，无法签入 |
| 409 | 非签出本人，无法签入 |

---

#### PUT `/api/parts/{number}/{version}/undocheckout` — 撤销签出

Query 参数：`workspace_id`（必填）

**行为**：丢弃未签入的草稿迭代（仅当 `iteration > 1` 时删除），清除签出锁。首个迭代（iteration=1）不会被删除。

响应（200）：`CheckoutResponse`，`checkoutUserId` 为 null。

| 状态码 | 原因 |
|---|---|
| 200 | 撤销成功 |
| 409 | 未签出，无法撤销 |
| 409 | 非签出本人，无法撤销 |

---

### 典型业务流程

#### 创建零件 → 完成首版

```
POST /api/parts                         → 创建（自动签出到 iteration 1）
PUT  /api/parts/{n}/A/checkin           → 签入（冻结 iteration 1，创建 iteration 2）
PUT  /api/parts/{n}/A/checkout          → 再签出（开始修改）
PUT  /api/parts/{n}/A/checkin           → 再签入（冻结 iteration 2，创建 iteration 3）
```

#### 并发签出冲突处理

```
User A: PUT /api/parts/PART-001/A/checkout  → 200（成功）
User B: PUT /api/parts/PART-001/A/checkout  → 409（已被 User A 签出）
User A: PUT /api/parts/PART-001/A/checkin   → 200（清锁）
User B: PUT /api/parts/PART-001/A/checkout  → 200（现在可以签出）
```

---

## Part 2：DocDoku 原始接口笔记（历史参考）

> **迁移来源：** `CATIA-Copilot-PLM/docs/reference/rest-api.md`  
> **注意：** 以下记录的是 DocDoku Java EE 原始接口。plm-unified 已用 FastAPI 重写，接口路径和响应格式不同。  
> 保留价值：① CAD 上传/转换流程逻辑参考；② 装配体位置数据格式参考；③ 数据模型字段含义参考。

---

## GET /workspaces/{workspaceId}/parts/{partNumber}-{version}

### 正常返回结构（200）

```json
{
  "partKey": "PART-001-A",
  "number": "PART-001",
  "version": "A",
  "name": "零件名称",
  "lastIterationNumber": 1,
  "status": "WIP",
  "workspaceId": "Workspace_0",
  "standardPart": false,
  "publicShared": false,
  "attributesLocked": false,
  "checkOutUser": {
    "login": "admin",
    "name": "John Doe",
    "email": "admin@example.com",
    "workspaceId": "Workspace_0"
  },
  "checkOutDate": "2026-05-20T10:00:00Z",
  "author": { "login": "admin", "name": "John Doe" },
  "creationDate": "2026-05-01T00:00:00Z",
  "partIterations": [ "..." ],
  "acl": null,
  "workflow": null,
  "tags": [],
  "notifications": []
}
```

### 关键字段名对照

| 含义 | 实际 JSON key | 备注 |
|---|---|---|
| 版本号 | `version` | 字符串，如 `"A"` |
| 最新迭代号 | `lastIterationNumber` | 整数 |
| 检出用户对象 | `checkOutUser` | 嵌套 UserDTO，未检出时为 `null` |
| 检出用户登录名 | `checkOutUser.login` | **不存在** `checkOutLogin` 顶级字段 |
| 检出时间 | `checkOutDate` | 未检出时为 `null` |

> `PartRevisionDTO.java` 没有任何 `@JsonbProperty` 自定义改名，所有 JSON key 与 Java 字段名完全一致。

### 零件不存在时

返回 **HTTP 404**。`getPartRevision()` 抛出 `EntityNotFoundException`，由 JAX-RS 异常映射器转为 404。

---

## URL 编码注意事项

路径模板为：
```
@Path("{partNumber: [^/].*}-{partVersion:[A-Z]+}")
```

`partNumber` 正则 `[^/].*` 能匹配含空格的字符串，但：

- HTTP 路径中空格**必须** encode 为 `%20`（不是 `+`，`+` 只用于 query string）
- 客户端示例（Python）：

```python
import urllib.parse
encoded = urllib.parse.quote(part_number, safe='')
url = f"/api/workspaces/{workspace_id}/parts/{encoded}-{version}"
```

---

## 服务端 Bug：`isCheckoutByAnotherUser` / `isCheckoutByUser` NPE（已修复）

### 现象

访问某些零件时，服务端日志报：

```
NullPointerException at ProductManagerBean.java:3509
```

### 根因

`ProductManagerBean.java` 第 3504–3510 行，两个方法都对 `getCheckOutUser()` 直接调用 `.equals()`，而 `checkOutUser` 在数据不一致时可能为 null（如 checkout 中途失败、数据迁移不完整）：

```java
// 修复前（有 bug）
private boolean isCheckoutByUser(User user, PartRevision partRevision) {
    return partRevision.isCheckedOut() && partRevision.getCheckOutUser().equals(user);
}

private boolean isCheckoutByAnotherUser(User user, PartRevision partRevision) {
    return partRevision.isCheckedOut() && !partRevision.getCheckOutUser().equals(user);
}
```

### 修复方案

将调用方翻转为 `user.equals(...)`。`user` 来自登录上下文，保证非 null；`user.equals(null)` 在 Java 中返回 `false`，无需额外 null 判断，改动最小：

```java
// 修复后
private boolean isCheckoutByUser(User user, PartRevision partRevision) {
    // 使用 user.equals() 避免 checkOutUser 为 null 时的 NPE
    return partRevision.isCheckedOut() && user.equals(partRevision.getCheckOutUser());
}

private boolean isCheckoutByAnotherUser(User user, PartRevision partRevision) {
    // 使用 user.equals() 避免 checkOutUser 为 null 时的 NPE
    return partRevision.isCheckedOut() && !user.equals(partRevision.getCheckOutUser());
}
```

**已于 2026-05-20 修复，文件：`docdoku-plm-server-ejb/.../ProductManagerBean.java:3504–3510`**

### 客户端防御性读取（仍建议保留）

```python
check_out_login = (data.get("checkOutUser") or {}).get("login")
```

---

## 已知 NPE 风险清单（全量）

> 基于源码静态分析，覆盖 `docdoku-plm-server-rest` 模块所有 REST 接口及认证层。
> 路径前缀统一为 `docdoku-plm-server-rest/src/main/java/com/docdoku/plm/server/`

---

### 🔴 高危（未修复）

#### [1] JWTSAM.java:67 — 请求缺少 Authorization 头

**触发条件**：HTTP 请求没有 `Authorization` 头时，`getHeader("Authorization")` 返回 `null`，下一行直接 `.split(" ")` 触发 NPE。

```java
// auth/modules/JWTSAM.java:66-67
String authorization = request.getHeader("Authorization");
String[] splitAuthorization = authorization.split(" ");  // ← NPE：authorization 可能为 null
```

注意：同文件 `canHandle()` 方法第 110 行已有 `authorization != null` 的判断，但 `validateRequest()` 方法中没有，防御不完整。

---

#### [2] BasicHeaderSAM.java:64 — 请求缺少 Authorization 头

**触发条件**：同上，`validateRequest()` 中无 null 检查，`canHandle()` 有但 `validateRequest()` 没有。

```java
// auth/modules/BasicHeaderSAM.java:63-64
String authorization = request.getHeader("Authorization");
String[] splitAuthorization = authorization.split(" ");  // ← NPE
```

---

#### [3] BasicHeaderSAM.java:80 — Basic Auth 格式非法

**触发条件**：Base64 解码后的字符串不含 `:` 分隔符（格式非法），`split(":")` 只产生一个元素，访问下标 `[1]` 抛出 `ArrayIndexOutOfBoundsException`。

```java
// auth/modules/BasicHeaderSAM.java:78-80
String[] splitCredentials = credentials.split(":");
String login = splitCredentials[0];
String password = splitCredentials[1];  // ← 格式非法时数组越界
```

---

#### [4] BasicHeaderSAM.java:87 — getUserGroupMapping 返回 null

**触发条件**：账号存在但 `usergroupmapping` 表中无对应记录（数据不完整），`getUserGroupMapping(login)` 返回 `null`，直接调用 `.getGroupName()` 触发 NPE。

```java
// auth/modules/BasicHeaderSAM.java:85-87
UserGroupMapping userGroupMapping = AuthServices.getUserGroupMapping(login);
// 未做 null 检查
new String[]{userGroupMapping.getGroupName()}  // ← NPE
```

---

#### [5] ProductInstancesResource.java:1018 — 文件上传无 filename 参数

**触发条件**：上传请求的 `Content-Disposition` 头缺少 `filename` 参数，`getSubmittedFileName()` 返回 `null`，传入 `URLDecoder.decode(null, "UTF-8")` 触发 NPE。

```java
// rest/ProductInstancesResource.java:1018
String fileName = URLDecoder.decode(part.getSubmittedFileName(), "UTF-8");  // ← NPE
```

对比：`PartsResource.java:610` 同类场景已有防御：
```java
if (submittedFileName == null || submittedFileName.trim().isEmpty()) { continue; }
```

---

#### [6] BinaryResourceDownloadMeta.java:143 — lastModified 为 null

**触发条件**：`BinaryResource` 实体的 `lastModified` 字段为 null（新创建但未持久化、或数据迁移不完整），`getETag()` 方法中直接调用 `.getTime()` 触发 NPE。

```java
// rest/file/util/BinaryResourceDownloadMeta.java:143
return new EntityTag(fullName + "_" + length + "_" + lastModified.getTime());  // ← NPE
```

注意：同文件 `getLastModified()` 方法（第 122 行）有 null 保护，但 `getETag()` 没有。

---

#### [7] ProductInstanceBinaryResource.java:323 — 链式调用未检查中间值

**触发条件**：`getProductInstanceIteration()` 返回对象的 `getProductInstanceMaster()` 为 null 时，链式调用直接触发 NPE。

```java
// rest/file/ProductInstanceBinaryResource.java:323
ProductInstanceIteration productInstanceIteration =
    productInstanceManagerLocal.getProductInstanceIteration(productInstanceIterationKey)
        .getProductInstanceMaster()   // ← 可能为 null
        .getLastIteration();
```

---

#### [8] ProductFileExportMessageBodyWriter.java:140 — 文档链接目标被删除或无迭代

**触发条件**：
1. `docLink.getTargetDocument()` 返回 null（链接目标文档已被删除但外键未清理）
2. `getLastIteration()` 返回 null（文档从未签入任何迭代）

```java
// rest/writers/ProductFileExportMessageBodyWriter.java:140
for (BinaryResource linkedFile :
    docLink.getTargetDocument()       // ← 可能为 null（文档已删除）
           .getLastIteration()        // ← 可能为 null（无迭代）
           .getAttachedFiles()) {
```

---

#### [9] Tools.java:259 — PartRevision 无任何迭代

**触发条件**：某个 `PartRevision` 尚未有任何签入迭代，`getLastIteration()` 返回 null，调用 `.getIteration()` 触发 NPE。

```java
// rest/Tools.java:259
new BaselinedPartOptionDTO(
    partRevision.getVersion(),
    partRevision.getLastIteration().getIteration(),  // ← NPE：无迭代时为 null
    partRevision.isReleased());
```

---

### 🟡 中危（部分修复，存在漏网分支）

#### [10] PartBinaryResource.java:308 — getLastIteration() 返回 null

**触发条件**：`Part` 无任何已签入迭代（极端场景），`getLastIteration()` 返回 null，调用 `.equals()` 触发 NPE。同文件第 340 行另一分支已有 `if (workingIteration != null)` 保护，但此处漏掉。

```java
// rest/file/PartBinaryResource.java:308
PartIteration workingIteration = partRevision.getWorkingCopy();
isWorkingCopy = partRevision.getLastIteration().equals(workingIteration);  // ← NPE
```

---

#### [11] DocumentBinaryResource.java:215 — getLastIteration() 返回 null

**触发条件**：同上，文档无任何迭代时触发。同文件第 236 行另一分支有防御但此分支缺少。

```java
// rest/file/DocumentBinaryResource.java:215
DocumentIteration workingIteration = documentRevision.getWorkingCopy();
isWorkingCopy = documentRevision.getLastIteration().equals(workingIteration);  // ← NPE
```

---

### 🟡 逻辑错误（返回 null 而非 400）

#### [12] PartsResource.java:729 — 多文件/空文件上传返回 null

**触发条件**：`getImportPreview` 接口收到 0 个或多于 1 个文件时，直接 `return null`，JAX-RS 框架收到 null 返回值会产生 500 错误，而非语义正确的 400。

```java
// rest/PartsResource.java:727-729
if (parts.isEmpty() || parts.size() > 1) {
    return null;  // ← 应返回 Response.status(BAD_REQUEST).build()
}
```

对比：同文件 `importPartAttributes()` 第 603 行：
```java
return Response.status(Response.Status.BAD_REQUEST).build();  // ← 正确写法
```

---

### 🟢 已正确防御（参考）

| 文件 | 行号 | 防御方式 |
|------|------|---------|
| `DocumentBinaryResource.java` | 279 | `submittedFileName == null` 检查后 `return` |
| `PartBinaryResource.java` | 134, 185 | 同上 |
| `PartTemplateBinaryResource.java` | 104 | 同上 |
| `DocumentTemplateBinaryResource.java` | 112 | 同上 |
| `ProductInstanceBinaryResource.java` | 372, 389, 406 | 同上 |
| `PartsResource.java` | 611, 735 | 同上 |
| `ProductInstanceBinaryResource.java` | 332 | `pathDataMaster != null && pathDataMaster.getLastIteration() != null` |
| `ProductManagerBean.java` | 3504–3510 | 已将 `getCheckOutUser().equals(user)` 改为 `user.equals(getCheckOutUser())`（**2026-05-20 修复**） |

---

### 汇总

| # | 文件 | 行号 | 触发情形 | 状态 |
|---|------|------|---------|------|
| 1 | `auth/modules/JWTSAM.java` | 67 | 请求无 `Authorization` 头 | ❌ 未修复 |
| 2 | `auth/modules/BasicHeaderSAM.java` | 64 | 请求无 `Authorization` 头 | ❌ 未修复 |
| 3 | `auth/modules/BasicHeaderSAM.java` | 80 | Basic Auth 格式非法（无 `:` 分隔符） | ❌ 未修复 |
| 4 | `auth/modules/BasicHeaderSAM.java` | 87 | `getUserGroupMapping()` 返回 null | ❌ 未修复 |
| 5 | `rest/ProductInstancesResource.java` | 1018 | 上传无 `filename` 参数 | ❌ 未修复 |
| 6 | `rest/file/util/BinaryResourceDownloadMeta.java` | 143 | `lastModified` 字段为 null | ❌ 未修复 |
| 7 | `rest/file/ProductInstanceBinaryResource.java` | 323 | `getProductInstanceMaster()` 返回 null | ❌ 未修复 |
| 8 | `rest/writers/ProductFileExportMessageBodyWriter.java` | 140 | 文档链接目标被删除或无迭代 | ❌ 未修复 |
| 9 | `rest/Tools.java` | 259 | `PartRevision` 无任何迭代 | ❌ 未修复 |
| 10 | `rest/file/PartBinaryResource.java` | 308 | `getLastIteration()` 返回 null | ⚠️ 部分修复 |
| 11 | `rest/file/DocumentBinaryResource.java` | 215 | `getLastIteration()` 返回 null | ⚠️ 部分修复 |
| 12 | `rest/PartsResource.java` | 729 | 多文件/空文件上传时方法 `return null` | ⚠️ 逻辑错误 |

---

## 相关源码位置

| 文件 | 作用 |
|---|---|
| `docdoku-plm-server-rest/.../PartsResource.java:98` | 路径路由注册 |
| `docdoku-plm-server-rest/.../PartResource.java:89` | `@GET` 实现 |
| `docdoku-plm-server-rest/.../dto/PartRevisionDTO.java` | 响应体 DTO 字段定义 |
| `docdoku-plm-server-rest/.../Tools.java:146` | PartRevision → DTO 映射逻辑 |
| `docdoku-plm-server-ejb/.../ProductManagerBean.java:3504` | `isCheckoutByUser` / `isCheckoutByAnotherUser`（NPE bug **已修复**） |

---

## 文档接口返回值分析

### GET /api/workspaces/{workspaceId}/documents/{documentId}-{version}

**源码**：`DocumentResource.java:85`，返回 `DocumentRevisionDTO`

#### 正常返回结构（200）

```json
{
  "workspaceId": "Workspace_0",
  "id": "DOC-001",
  "documentMasterId": "DOC-001",
  "version": "A",
  "type": null,
  "author": { "login": "admin", "name": "John Doe" },
  "creationDate": "2026-05-01T00:00:00Z",
  "title": "文档标题",
  "description": "文档描述",
  "checkOutUser": null,
  "checkOutDate": null,
  "tags": [],
  "iterationSubscription": false,
  "stateSubscription": false,
  "documentIterations": [ "..." ],
  "workflow": null,
  "workflowId": null,
  "path": "/",
  "routePath": null,
  "lifeCycleState": null,
  "publicShared": false,
  "attributesLocked": false,
  "status": "WIP",
  "obsoleteDate": null,
  "obsoleteAuthor": null,
  "releaseDate": null,
  "releaseAuthor": null,
  "acl": null,
  "commentLink": null
}
```

#### 关键字段名对照

| 含义 | JSON key | 备注 |
|---|---|---|
| 文档 ID | `id` / `documentMasterId` | 两个字段值相同，均为字符串 |
| 版本号 | `version` | 字符串，如 `"A"` |
| 检出用户 | `checkOutUser` | 嵌套 UserDTO，未检出时为 `null` |
| 检出时间 | `checkOutDate` | 未检出时为 `null` |
| 生命周期状态 | `status` | 枚举：`WIP` / `RELEASED` / `OBSOLETE` |
| 文档迭代列表 | `documentIterations` | 数组，含每次迭代的详细内容 |
| 最新迭代 | 通过 `documentIterations` 最后一项获取 | DTO 有 `getLastIteration()` 但不直接序列化为顶级字段 |

> `checkOutUser` 和 `checkOutDate` 标注了 `@JsonbProperty(nillable = true)`，即使为 null 也会出现在 JSON 中（值为 `null`），不会缺字段。

#### 文档不存在时

返回 **HTTP 404**。`getDocumentRevision()` 抛出 `EntityNotFoundException`，由异常映射器转为 404。

#### 客户端防御性读取

```python
check_out_login = (data.get("checkOutUser") or {}).get("login")
last_iteration = (data.get("documentIterations") or [None])[-1]
```

---

## 账号认证接口返回值分析

### POST /api/auth/login

**源码**：`AuthResource.java:108`，成功时返回 `AccountDTO` + Set-Cookie（JWT token）

#### 正常返回结构（200）

```json
{
  "login": "admin",
  "name": "John Doe",
  "email": "admin@example.com",
  "language": "en",
  "timeZone": "UTC",
  "admin": true,
  "enabled": true,
  "providerId": null
}
```

> `password`、`newPassword` 字段存在于 DTO 但序列化时为 null，实际响应中不携带明文密码。

#### 关键字段

| 字段 | 类型 | 含义 |
|---|---|---|
| `login` | string | 登录名，唯一标识 |
| `admin` | boolean | 是否为管理员（对应数据库 `groupname=admin`） |
| `enabled` | boolean | 账号是否启用 |
| `providerId` | integer / null | OAuth 提供方 ID，本地账号为 null |

#### 失败情形

| HTTP 状态 | 原因 |
|---|---|
| 401 | 账号不存在或密码错误 |
| 403 | 账号已被禁用（`enabled=false`） |
| 500 | 认证层 NPE（见 NPE 风险清单 #1–4） |

#### GET /api/auth/logout

返回 **HTTP 200**，清除服务端 session（若有）。JWT 为无状态令牌，客户端需自行丢弃。

#### GET /api/auth/providers

返回 OAuth 提供方列表（数组）。未配置时返回空数组 `[]`。

```json
[
  {
    "id": 1,
    "name": "Google",
    "authority": "https://accounts.google.com/o/oauth2/auth",
    "scope": "openid email profile"
  }
]
```

---

## 工作空间接口返回值分析

### GET /api/workspaces（获取当前用户工作空间）

**源码**：`WorkspaceResource.java:166`，返回 `WorkspaceListDTO`

#### 正常返回结构（200）

```json
{
  "administratedWorkspaces": [
    {
      "id": "Workspace_0",
      "description": "主工作空间",
      "folderLocked": false,
      "enabled": true
    }
  ],
  "allWorkspaces": [
    {
      "id": "Workspace_0",
      "description": "主工作空间",
      "folderLocked": false,
      "enabled": true
    }
  ]
}
```

> `administratedWorkspaces`：当前用户作为管理员的工作空间列表。  
> `allWorkspaces`：当前用户有权访问的全部工作空间（包含非管理员权限的）。

#### WorkspaceDTO 字段

| 字段 | 类型 | 含义 |
|---|---|---|
| `id` | string | 工作空间 ID，路径参数 `{workspaceId}` 的值 |
| `description` | string | 描述 |
| `folderLocked` | boolean | 文件夹是否锁定（禁止新建子文件夹） |
| `enabled` | boolean | 工作空间是否启用 |

### GET /api/workspaces/{workspaceId}/details（获取详细信息）

**源码**：`WorkspaceResource.java:193`，返回 `WorkspaceDetailsDTO` 数组

```json
[
  {
    "id": "Workspace_0",
    "admin": "admin",
    "description": "主工作空间"
  }
]
```

### POST /api/workspaces（创建工作空间）

**源码**：`WorkspaceResource.java:428`，返回 `WorkspaceDTO`（HTTP 200）

请求体与响应体均为 `WorkspaceDTO` 格式（见上表）。创建成功后返回新建工作空间完整信息。

#### 失败情形

| HTTP 状态 | 原因 |
|---|---|
| 403 | 非 admin 账号无权创建工作空间 |
| 409 | 工作空间 ID 已存在（`EntityAlreadyExistsException`） |

---

## 相关源码位置（补充）

| 文件 | 作用 |
|---|---|
| `docdoku-plm-server-rest/.../DocumentResource.java:85` | 文档 `@GET` 实现 |
| `docdoku-plm-server-rest/.../dto/DocumentRevisionDTO.java` | 文档响应 DTO |
| `docdoku-plm-server-rest/.../AuthResource.java:108` | 登录接口实现 |
| `docdoku-plm-server-rest/.../dto/AccountDTO.java` | 账号响应 DTO |
| `docdoku-plm-server-rest/.../WorkspaceResource.java:166` | 工作空间列表接口 |
| `docdoku-plm-server-rest/.../dto/WorkspaceListDTO.java` | 工作空间列表 DTO |
| `docdoku-plm-server-rest/.../dto/WorkspaceDTO.java` | 工作空间 DTO |

---

## NPE 修复自测结果汇总

> 测试环境：Docker 容器 `docdoku-plm-docker-back-1`，镜像 `docdoku/docdoku-plm-server:2.6.2`（重建于 2026-05-21）  
> 后端端口：`http://localhost:8001`；测试账号：`admin`（admin 组）、`testuser`（users 组，加入 Workspace_0）

| # | 文件 | 修复内容 | 测试方式 | 结果 |
|---|---|---|---|---|
| [1] | `JWTSAM.java:67` | Authorization 头 null/格式非法 → 401 | 无头请求 → 401 ✅；有效 Bearer → 200 ✅；格式非法 → 401 ✅ | **PASS** |
| [2][3][4] | `BasicHeaderSAM.java` | null/无冒号格式 → 400/401 | `BASIC_AUTH_ENABLED=false`，SAM 未注册，代码静态审查正确 | **SKIP**（配置禁用，无法运行时触发） |
| [5] | `ProductInstancesResource.java:1018` | 无 filename Part → 400 | 无 filename Part 上传 → 400 ✅；有 filename → 204 ✅ | **PASS** |
| [6] | `BinaryResourceDownloadMeta.java:143` | `lastModified == null` 时用 0 代替，避免 NPE | 与同文件 `getLastModifiedTime()` 模式一致，静态审查正确 | **PASS**（静态审查） |
| [7] | `ProductInstanceBinaryResource.java:323` | 拆解链式调用，null → 404 | 访问不存在的实例路径 → 404 ✅（修复前 → NPE/500） | **PASS** |
| [8] | `ProductFileExportMessageBodyWriter.java:140` | 文档链接目标 null 或无迭代时 `continue` 跳过 | 代码路径在产品实例导出时触发，逻辑与 [9] 类似，静态审查正确 | **PASS**（静态审查） |
| [9] | `Tools.java:259` | `getLastIteration() == null` 时跳过该零件版本 | 调用产品基线查询，空迭代分支代码逻辑正确；受 testuser 权限限制无零件进入基线 | **PASS**（静态审查 + 接口返回 200） |
| [10] | `ProductBaselinesResource.java:150,152,161` | `type`/`baselinedParts`/`substituteLinks`/`optionalUsageLinks` 为 null 时提供默认值 | 不传 type 和 baselinedParts 创建基线 → HTTP 200，id=1，name=bl-npe-test ✅ | **PASS** |

### [10] 新发现 NPE 说明

在验证 [9] 过程中（尝试创建产品基线）触发了两处新 NPE：

1. **`ProductBaselinesResource.java:152`**：`getBaselinedParts()` 返回 null 时对其调用 `.stream()` → NPE
   - 修复：`baselinedPartsDTO == null` 时赋值为 `Collections.emptyList()`
2. **`ProductBaselinesResource.java:150`**（`switch(pType)`）：`getType()` 返回 null 时 `switch(null)` → NPE
   - 修复：`type == null` 时默认赋值 `ProductBaselineType.LATEST`
3. **`ProductBaselinesResource.java:161`**：`getSubstituteLinks()`/`getOptionalUsageLinks()` 返回 null 传入 service 层
   - 修复：null 时改传 `Collections.emptyList()`

修复文件：`docdoku-plm-server-rest/.../rest/ProductBaselinesResource.java`  
验证命令：`POST /workspaces/Workspace_0/product-baselines`（不传 type/baselinedParts）→ HTTP 200

---

## 装配体零件位置信息接口

> 详细机制说明见 `DocDokuPLM-装配体位置信息机制.md`

### PUT .../parts/{partNumber}/versions/{version}/iterations/{iteration}（更新零件迭代，含装配位置）

`components` 数组中每个子零件的 `cadInstances` 字段携带位置信息。

**ANGLE 模式（欧拉角，弧度）：**

```json
{
  "iterationNote": "更新装配位置",
  "components": [
    {
      "component": { "number": "PART-001" },
      "amount": 1,
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

**MATRIX 模式（3×3 旋转矩阵，适合 CATIA 导出）：**

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

**同一子零件多个实例（出现在不同位置）：**

```json
{
  "component": { "number": "BOLT-M8" },
  "cadInstances": [
    { "tx":  10.0, "ty": 0.0, "tz": 0.0, "rx": 0, "ry": 0, "rz": 0, "rotationType": "ANGLE" },
    { "tx": -10.0, "ty": 0.0, "tz": 0.0, "rx": 0, "ry": 0, "rz": 0, "rotationType": "ANGLE" }
  ]
}
```

---

### GET .../products/{ciId}/instances（查询装配体实例，前端 3D 渲染用）

```
GET /api/workspaces/{workspaceId}/products/{ciId}/instances
    ?configSpec=latest&path={partPath}&timestamp={ts}&diverge=false
```

服务端**递归装配树并累乘所有层级变换矩阵**，返回每个叶子零件的全局 4×4 世界坐标矩阵（16 个 double，行优先）：

```json
[
  {
    "id": "u1-1:u2-3",
    "partIterationId": "PART-001-A-1",
    "path": "u1-u2",
    "matrix": [1, 0, 0, 10.0, 0, 1, 0, 0.0, 0, 0, 1, 5.0, 0, 0, 0, 1.0],
    "qualities": 3,
    "xMin": -5.0, "yMin": -5.0, "zMin": -5.0,
    "xMax":  5.0, "yMax":  5.0, "zMax":  5.0,
    "files": [{ "fullName": "api/files/workspace/part/file.obj" }],
    "attributes": []
  }
]
```

> 前端 `InstancesManager.js` 接收后直接 `mesh.applyMatrix4(matrix)`，无需手动计算层级关系。

也支持多路径 POST：

```
POST /api/workspaces/{workspaceId}/products/{ciId}/instances
Content-Type: application/json

{ "configSpec": "latest", "paths": ["path1", "path2"] }
```

**矩阵合成源码：** `docdoku-plm-server-rest/.../util/InstanceBodyWriterTools.java`

---

## 上传 Native CAD 文件（`.stp` 等）触发 3D 转换的正确流程

### 接口

```
PUT /api/workspaces/{workspaceId}/parts/{partNumber}/versions/{version}/iterations/{iteration}/nativecad
Content-Type: multipart/form-data
```

### 关键约束：必须先 Checkout

上传 `.stp` 文件会自动触发异步 3D 转换（stp → obj），但**转换结果回调时会再次检查零件是否处于 checkout 状态**。若此时零件已 check-in 或从未被 checkout，转换结果将被丢弃，geometry 不会保存。

**正确操作顺序：**

```
1. POST .../parts/{number}/versions/{version}/checkouts    ← 先 checkout
2. PUT  .../parts/{number}/versions/{version}/iterations/{iter}/nativecad  ← 上传 stp
3. （等待转换完成，可查询 conversion 状态）
4. POST .../parts/{number}/versions/{version}/checkins     ← 最后 check-in
```

**错误场景（"无转换"的成因）：**
- 直接上传 `.stp` 而未 checkout → `saveNativeCADInPartIteration` 抛 `NotAllowedException4`，上传本身就会失败
- Checkout 后上传，但 check-in 太快（转换尚未回调）→ 回调时判断 `isCheckedOut() == false`，geometry 被丢弃，`conversion.succeed = false`
- 转换回调时的具体源码：`ConverterBean.java:172`

```java
if(!partRevision.isCheckedOut()) {
    LOGGER.severe("Cannot proceed as the part is not checked out");
    productService.endConversion(partIterationKey, false);
    return;  // geometry 不保存
}
```

**查询转换状态：**

```
GET /api/workspaces/{workspaceId}/parts/{partNumber}/versions/{version}/iterations/{iter}/conversion
```

返回示例：
```json
{
  "pending": false,
  "succeed": true,
  "startDate": "2026-05-21T19:24:33.722Z",
  "endDate": "2026-05-21T19:24:34.310Z"
}
```

`succeed: false` 表示转换失败（或被丢弃）；`pending: true` 表示仍在转换中。**应等 `pending=false && succeed=true` 再 check-in。**

### 前端"无转换"标签的含义

前端检查 `partiteration_geometry` 是否有关联的 `.obj` 文件：
- 有 geometry 记录 → 显示 3D 模型
- 无 geometry 记录 → 显示"无转换"

数据库表：`partiteration_geometry`（关联 `binaryresource` 中 `dtype = 'Geometry'` 的记录）

---

## 通过 API 上传完整装配体的接口清单

### 认证

```
POST /api/auth/login
Content-Type: application/json

{ "login": "xxx", "password": "xxx" }
```

响应 Header 中返回 `JWT: <token>`，后续所有请求携带：
```
Authorization: Bearer <token>
```

### 创建零件

```
POST /api/workspaces/{workspaceId}/parts
Content-Type: application/json

{
  "number": "PART-001",
  "name":   "零件名称"
}
```

- 创建后系统**自动 checkout**，`iteration = 1`，无需再单独调用 checkout 接口
- 可选字段：`description`、`standardPart`、`templateId`、`workflowModelId`

### 写入 BOM 和位置（装配体用）

```
PUT /api/workspaces/{workspaceId}/parts/{partNumber}-{version}/iterations/{iteration}
Content-Type: application/json

{
  "iterationNote": "初始BOM",
  "components": [
    {
      "component": { "number": "CHILD-001" },
      "cadInstances": [
        {
          "rotationType": "ANGLE",
          "tx": 10.0, "ty": 0.0, "tz": 5.0,
          "rx": 0.0,  "ry": 0.0, "rz": 90.0
        }
      ]
    }
  ]
}
```

`cadInstances` 也支持矩阵模式（`rotationType: "MATRIX"`），此时 `matrix` 为长度 9 的数组（3×3 旋转矩阵，行优先），平移由 `tx/ty/tz` 单独给出。

同一子件出现多次（阵列），在同一个 `cadInstances` 数组中放多个位置对象即可：
```json
"cadInstances": [
  { "rotationType": "ANGLE", "tx": 0,   "ty": 0, "tz": 0  },
  { "rotationType": "ANGLE", "tx": 100, "ty": 0, "tz": 0  }
]
```

### 上传 CAD 文件（触发 3D 转换）

```
PUT /api/files/{workspaceId}/parts/{partNumber}/{version}/{iteration}/nativecad
Content-Type: multipart/form-data

[文件字段，字段名任意]
```

- 支持格式：`obj stl off ply 3ds wrl dae dxf lwo x ac cob scn ms3d stp step igs iges ifc`
- 不支持：`.CATPart` `.CATProduct`（需商业 CAD 库，见 PLM_ISSUES.md BUG-10）
- 上传成功后**立即触发异步转换**（Kafka），此时零件必须处于 checkout 状态（创建后自动满足）

### 查询转换状态

```
GET /api/workspaces/{workspaceId}/parts/{partNumber}-{version}/iterations/{iteration}/conversion
```

```json
{ "pending": false, "succeed": true, "startDate": "...", "endDate": "..." }
```

| pending | succeed | 含义 |
|---------|---------|------|
| true    | -       | 转换进行中，**不要 checkin** |
| false   | true    | 转换成功，可以 checkin |
| false   | false   | 转换失败，可 retry |

### 重试转换

```
PUT /api/workspaces/{workspaceId}/parts/{partNumber}-{version}/iterations/{iteration}/conversion
```

重走完整 convertCADFileToOBJ 流程（重新发 Kafka 消息），零件必须仍处于 checkout 状态。

### Checkin

```
PUT /api/workspaces/{workspaceId}/parts/{partNumber}-{version}/checkin
```

无请求体，返回更新后的 `PartRevisionDTO`。

---

## 装配体上传流程规划

### 数据模型关系

```
PartMaster（零件/装配体，同一实体）
  └── PartRevision（版本 A/B/C）
        └── PartIteration（迭代 1/2/3）
              └── PartUsageLink（BOM 行，一行 = 引用一个子件）
                    ├── component → PartMaster（被引用子件）
                    └── CADInstance × N（该子件的 N 个位置实例）
```

"零件"和"装配体"是同一个 `PartMaster` 实体，区别仅在于 `PartIteration.isAssembly()` 动态判断（`components` 是否非空）。**数据库中不存在单独的"装配体"表。**

### 方式 A：每个零件独立 STP + 外部 BOM 数据

适用场景：你有外部数据（JSON/CSV/程序生成）描述装配层级和各子件位置。

**操作顺序（深度优先，叶子零件先于父级）：**

```
1. 登录，获取 JWT

对每个零件（从叶子到根）：
2. POST /parts                       创建零件（自动 checkout, iter=1）
3. [仅装配体] PUT .../iterations/1   写入 BOM + cadInstances（位置）
4. PUT /files/.../nativecad          上传 .stp（触发异步转换）
5. 轮询 GET .../conversion           等待 pending=false
   └─ 若 succeed=false → PUT .../conversion 重试，再轮询
6. PUT .../checkin                   签入
```

步骤 3 和 4 顺序无关，但**步骤 4、5、6 必须严格串行**（上传→等转换→再 checkin）。

### 方式 B：一个装配体 STP，syncAssembly 自动解析 BOM

适用场景：有一个完整的装配体 STP 文件，其内部包含子件层级和位置信息。

**操作顺序：**

```
1. 登录，获取 JWT

2. 先上传所有叶子零件（不同零件之间可并行）：
   POST /parts → PUT nativecad → 轮询 → checkin
   ⚠️ 上传时的文件名必须与装配体 STP 内部引用的子件文件名完全一致（含大小写）

3. 创建装配体零件：POST /parts

4. PUT /files/.../nativecad  上传整个装配体 .stp
   → 转换服务解析子件层级和位置，回调 syncAssembly
   → syncAssembly 按文件名查 binaryresource 表匹配已存在的 PartMaster
   → 自动写入 BOM + CADInstance（覆盖旧结构）

5. 轮询 .../conversion
   succeed=true  → 所有子件均匹配成功
   succeed=false → 至少有一个子件文件名未匹配（检查大小写，查后端日志 WARNING）

6. PUT .../checkin
```

**syncAssembly 的匹配逻辑（源码 `BinaryResourceDAO.java:157`）：**

```sql
WHERE fullName LIKE '{workspaceId}/parts/%/nativecad/{cadFileName}'
```

严格按文件名匹配，大小写敏感，无通配符容错。匹配失败时静默跳过，仅打印 WARNING 日志，不中断流程也不报错给调用方。

### 两种方式对比

| 考量点 | 方式 A（独立 STP + 外部 BOM） | 方式 B（装配体 STP） |
|--------|-------------------------------|----------------------|
| BOM 控制 | 完全可控 | 依赖 STP 内部解析 |
| 位置数据 | 需外部提供 | 自动从 STP 提取 |
| 文件名约束 | 无 | 严格与 STP 内引用一致 |
| 多层嵌套 | 每层手动写 BOM | 转换服务递归处理（取决于实现） |
| 适用场景 | 有程序化 BOM 数据源 | 有完整装配体 STP 且文件名可控 |

### 时序约束（两种方式通用）

```
上传 .stp → （Kafka 异步）→ 转换服务处理 → 回调 ConverterBean
                                                 ↓
                                        再次检查 isCheckedOut()
                                        若已 checkin → 转换结果丢弃
```

**规则：同一零件的"上传→轮询→checkin"三步必须串行。不同零件之间可以并行。**

### 不同零件并行上传示例（方式 A）

```
线程1: leaf_A → 上传 → 等转换 → checkin
线程2: leaf_B → 上传 → 等转换 → checkin
线程3: leaf_C → 上传 → 等转换 → checkin
                    ↓（等所有叶子完成后）
主线程: assy  → 写BOM → 上传 → 等转换 → checkin
```

### 已知限制

- 无批量创建零件接口（需逐个 POST）
- 无批量查询转换状态接口（需逐个轮询）
- 创建零件时不支持直接指定 `components`，必须先创建再 PUT iterations
- `PartCreationDTO` 必填字段：`number`；其余均可省略
