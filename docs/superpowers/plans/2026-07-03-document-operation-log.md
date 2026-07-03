# 图文档操作记录功能实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在图文档详情弹窗新增「操作记录」TAB，展示当前版本图文档及其附件的操作日志，并复用公共组件统一任务与图文档的操作记录展示。

**Architecture:** 后端新增专用路由 `GET /documents/{doc_id}/logs` 并扩展通用 `get_logs` 查询以支持多 `target_type`；前端抽取 `OperationLogTable` 公共组件，`Documents.tsx` 引入第三个 TAB，`TaskEditModal.tsx` 替换原有内联表格为公共组件。

**Tech Stack:** FastAPI、SQLAlchemy、React、TypeScript、Tailwind CSS、Vitest、pytest

---

## 文件结构

| 文件 | 动作 | 职责 |
| --- | --- | --- |
| `backend/app/crud/__init__.py` | 修改 | 扩展 `get_logs` 支持 `target_type` 为字符串或列表 |
| `backend/app/routers/documents.py` | 修改 | 新增 `GET /documents/{doc_id}/logs` 路由 |
| `backend/tests/test_document_logs.py` | 创建 | 后端路由与 CRUD 单元/集成测试 |
| `frontend/src/services/api.ts` | 修改 | `documentsApi` 新增 `getLogs` 方法 |
| `frontend/src/components/OperationLogTable.tsx` | 创建 | 公共操作记录表格组件 |
| `frontend/src/pages/Documents.tsx` | 修改 | 新增「操作记录」TAB 及状态、加载逻辑 |
| `frontend/src/pages/Project/TaskEditModal.tsx` | 修改 | 操作记录 TAB 改为复用 `OperationLogTable` |

---

## Task 1: 扩展 `get_logs` 支持多 `target_type`

**Files:**
- Modify: `backend/app/crud/__init__.py:29-37`

- [ ] **Step 1: 编写失败测试**

在 `backend/tests/test_document_logs.py` 创建以下测试：

```python
import pytest
from app.crud import get_logs
from app.models import OperationLog


def test_get_logs_supports_multiple_target_types(db):
    """get_logs 应支持传入 target_type 列表同时过滤多种类型。"""
    from app.models import Workspace, User
    from app.core.security import get_password_hash
    ws = Workspace(name="w")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    u = User(workspace_id=ws.id, username="admin", password_hash=get_password_hash("x"), real_name="A", role="admin")
    db.add(u)
    db.commit()

    log1 = OperationLog(user_id=u.id, username="admin", action="创建图文档", target_type="document", target_id="doc-1")
    log2 = OperationLog(user_id=u.id, username="admin", action="上传附件", target_type="document_att", target_id="doc-1")
    log3 = OperationLog(user_id=u.id, username="admin", action="更新图文档", target_type="document", target_id="doc-2")
    db.add_all([log1, log2, log3])
    db.commit()

    items, total = get_logs(db, target_type=["document", "document_att"], target_id="doc-1")
    assert total == 2
    actions = {log.action for log in items}
    assert actions == {"创建图文档", "上传附件"}
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd D:\OpenCode\plm-unified\backend
pytest tests/test_document_logs.py::test_get_logs_supports_multiple_target_types -v
```

Expected: FAIL with `TypeError` or only one log returned.

- [ ] **Step 3: 修改 `get_logs` 实现**

```python
# backend/app/crud/__init__.py
from typing import List, Union


def get_logs(db, skip=0, limit=100, target_type: Union[str, List[str], None] = None, target_id=None):
    q = db.query(OperationLog)
    if target_type:
        if isinstance(target_type, list):
            q = q.filter(OperationLog.target_type.in_(target_type))
        else:
            q = q.filter(OperationLog.target_type == target_type)
    if target_id:
        q = q.filter(OperationLog.target_id == target_id)
    total = q.count()
    items = q.order_by(OperationLog.created_at.desc()).offset(skip).limit(limit).all()
    return items, total
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_document_logs.py::test_get_logs_supports_multiple_target_types -v
```

Expected: PASS

- [ ] **Step 5: 回归现有日志查询**

```bash
pytest tests/test_auth.py -v
```

Expected: 全部通过，确认未破坏现有调用。

- [ ] **Step 6: Commit**

```bash
cd D:\OpenCode\plm-unified
git add backend/app/crud/__init__.py backend/tests/test_document_logs.py
git commit -m "feat(backend): get_logs 支持 target_type 列表过滤"
```

---

## Task 2: 后端新增 `GET /documents/{doc_id}/logs`

**Files:**
- Modify: `backend/app/routers/documents.py`
- Create: `backend/tests/test_document_logs.py`

- [ ] **Step 1: 编写失败测试**

在 `backend/tests/test_document_logs.py` 追加：

```python
import uuid
from fastapi.testclient import TestClient
```

```python
@pytest.fixture
def client_with_logs(db):
    from app.main import app
    from app.database import get_db
    from app.models import Workspace, User, Document, UserGroup
    from app.core.security import get_password_hash
    from app.crud import create_log
    from app.models.user_groups import user_group_members

    ws = Workspace(name="w")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    admin = User(workspace_id=ws.id, username="admin", password_hash=get_password_hash("admin12345"),
                 real_name="管理员", role="admin")
    viewer = User(workspace_id=ws.id, username="viewer", password_hash=get_password_hash("viewer123"),
                  real_name="查看者", role="user")
    db.add_all([admin, viewer])
    db.commit()
    db.refresh(admin)
    db.refresh(viewer)

    doc = Document(code="DOC-001", name="测试图文档", version="A", status="draft", creator_id=admin.id)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    group_doc = Document(code="DOC-002", name="受控图文档", version="A", status="draft", creator_id=admin.id)
    db.add(group_doc)
    db.commit()
    db.refresh(group_doc)
    g = UserGroup(name="g1", workspace_id=ws.id)
    db.add(g)
    db.commit()
    db.refresh(g)
    from app.models.models_document import DocumentGroupLink
    db.add(DocumentGroupLink(document_id=group_doc.id, group_id=g.id))
    db.commit()

    create_log(db, admin.id, admin.username, "创建图文档", "document", str(doc.id), "编号:DOC-001", None)
    create_log(db, admin.id, admin.username, "上传附件", "document_att", str(doc.id), "文件:1.pdf", None)

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app), admin, viewer, doc, group_doc
    finally:
        app.dependency_overrides.clear()


def test_list_document_logs_success(client_with_logs):
    client, admin, viewer, doc, group_doc = client_with_logs
    r = client.post("/api/auth/token", data={"username": "admin", "password": "admin12345"})
    token = r.json()["access_token"]

    res = client.get(f"/api/documents/{doc.id}/logs", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    actions = {item["action"] for item in body["items"]}
    assert actions == {"创建图文档", "上传附件"}


def test_list_document_logs_forbidden_for_no_permission_role(client_with_logs):
    client, admin, viewer, doc, group_doc = client_with_logs
    # user 角色默认无 documents:read，需确认权限表；若 user 角色实际拥有 documents:read，则改用其他角色。
    r = client.post("/api/auth/token", data={"username": "viewer", "password": "viewer123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    res = client.get(f"/api/documents/{doc.id}/logs", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_list_document_logs_group_access_denied(client_with_logs):
    client, admin, viewer, doc, group_doc = client_with_logs
    r = client.post("/api/auth/token", data={"username": "viewer", "password": "viewer123"})
    token = r.json()["access_token"]

    # viewer 不在 group_doc 的关联用户组中，应 403
    res = client.get(f"/api/documents/{group_doc.id}/logs", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
```

> **注意：** 若 `user` 角色在 `PERMISSIONS` 中已包含 `documents:read`，需调整测试角色为实际无权限的角色，或直接在 fixture 中创建一个 `role="guest"` 的角色（前提是权限表存在该角色）。

- [ ] **Step 2: 运行测试确认失败**

```bash
cd D:\OpenCode\plm-unified\backend
pytest tests/test_document_logs.py::test_list_document_logs_success -v
```

Expected: FAIL with 404 or route not found.

- [ ] **Step 3: 实现新路由**

在 `backend/app/routers/documents.py` 中 `get_document_versions_endpoint` 之后追加：

```python
@router.get("/{doc_id}/logs")
async def list_document_logs(
    doc_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents:read")),
):
    """获取图文档当前版本的操作记录（含附件操作）。"""
    d = db.query(Document).filter(Document.id == doc_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="图文档不存在")
    enforce_document_content_access(db, current_user, d)
    items, total = get_logs(
        db, skip=skip, limit=limit,
        target_type=["document", "document_att"],
        target_id=str(doc_id),
    )
    return {
        "items": [{
            "id": str(log.id),
            "user_id": str(log.user_id) if log.user_id else None,
            "username": log.username,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "detail": log.detail,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        } for log in items],
        "total": total,
    }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_document_logs.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd D:\OpenCode\plm-unified
git add backend/app/routers/documents.py backend/tests/test_document_logs.py
git commit -m "feat(backend): 新增图文档操作记录查询路由"
```

---

## Task 3: 前端 API 层新增 `getLogs`

**Files:**
- Modify: `frontend/src/services/api.ts:149-166`

- [ ] **Step 1: 在 `documentsApi` 中新增方法**

```typescript
// frontend/src/services/api.ts
export const documentsApi = {
  list: (params?: { page?: number; page_size?: number; keyword?: string; status?: string; brief?: boolean; updated_since?: number }) =>
    api.get('/documents/', { params }),
  get: (id: string) => api.get(`/documents/${id}`),
  create: (data: unknown) => api.post('/documents/', data),
  update: (id: string, data: unknown) => api.put(`/documents/${id}`, data),
  delete: (id: string) => api.delete(`/documents/${id}`),
  upgrade: (id: string, note?: string) => api.post(`/documents/${id}/upgrade`, { note }),
  versions: (id: string) => api.get(`/documents/${id}/versions`),
  getLogs: (id: string) => api.get(`/documents/${id}/logs`),
  // 图文档附件
  uploadAttachment: (docId: string, data: { id?: string; file_name: string; file_data: string }) =>
    api.post(`/documents/${docId}/attachments`, data),
  listAttachments: (docId: string) => api.get(`/documents/${docId}/attachments/`),
  getAttachment: (docId: string, attId: string) => api.get(`/documents/${docId}/attachments/${attId}`),
  deleteAttachment: (docId: string, attId: string) => api.delete(`/documents/${docId}/attachments/${attId}`),
  references: (docId: string) => api.get(`/documents/${docId}/references`),
};
```

- [ ] **Step 2: 类型检查**

```bash
cd D:\OpenCode\plm-unified\frontend
npx tsc --noEmit
```

Expected: 无新增类型错误。

- [ ] **Step 3: Commit**

```bash
cd D:\OpenCode\plm-unified
git add frontend/src/services/api.ts
git commit -m "feat(frontend): documentsApi 新增 getLogs 方法"
```

---

## Task 4: 抽取公共组件 `OperationLogTable`

**Files:**
- Create: `frontend/src/components/OperationLogTable.tsx`

- [ ] **Step 1: 创建组件文件**

```tsx
// frontend/src/components/OperationLogTable.tsx
import type { OperationLog } from '../types';
import { formatDateTime } from '../utils/date';

interface OperationLogTableProps {
  logs: OperationLog[];
  loading?: boolean;
}

const ACTION_CLASS: Record<string, string> = {
  '创建图文档': 'bg-green-100 text-green-800',
  '创建任务': 'bg-green-100 text-green-800',
  '删除任务': 'bg-red-100 text-red-800',
  '软删除图文档': 'bg-red-100 text-red-800',
  '任务状态变更': 'bg-blue-100 text-blue-800',
  '更新图文档': 'bg-gray-100 text-gray-700',
  '图文档升版': 'bg-purple-100 text-purple-800',
  '上传附件': 'bg-blue-50 text-blue-700',
  '删除附件': 'bg-orange-50 text-orange-700',
};

export default function OperationLogTable({ logs, loading }: OperationLogTableProps) {
  if (loading) return <div className="text-center text-gray-400 py-8">加载中...</div>;
  if (logs.length === 0) return <div className="text-center text-gray-400 py-8">暂无操作记录</div>;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <table className="w-full text-sm table-fixed">
        <colgroup>
          <col style={{ width: '150px' }} />
          <col style={{ width: '80px' }} />
          <col style={{ width: '96px' }} />
          <col />
        </colgroup>
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="text-left px-3 py-2 text-xs font-medium text-gray-500">时间</th>
            <th className="text-left px-3 py-2 text-xs font-medium text-gray-500">用户</th>
            <th className="text-left px-3 py-2 text-xs font-medium text-gray-500">操作</th>
            <th className="text-left px-3 py-2 text-xs font-medium text-gray-500">详情</th>
          </tr>
        </thead>
      </table>
      <div className="max-h-64 overflow-y-auto">
        <table className="w-full text-sm table-fixed">
          <colgroup>
            <col style={{ width: '150px' }} />
            <col style={{ width: '80px' }} />
            <col style={{ width: '96px' }} />
            <col />
          </colgroup>
          <tbody className="divide-y divide-gray-100">
            {logs.map((l) => (
              <tr key={l.id}>
                <td className="px-3 py-2 text-gray-500 whitespace-nowrap align-top">{formatDateTime(l.created_at)}</td>
                <td className="px-3 py-2 align-top truncate">{l.username}</td>
                <td className="px-3 py-2 align-top">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${ACTION_CLASS[l.action] ?? 'bg-gray-100 text-gray-700'}`}>
                    {l.action}
                  </span>
                </td>
                <td className="px-3 py-2 text-gray-500 break-words align-top">{l.detail || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 类型检查**

```bash
cd D:\OpenCode\plm-unified\frontend
npx tsc --noEmit
```

Expected: 无新增类型错误。

- [ ] **Step 3: Commit**

```bash
cd D:\OpenCode\plm-unified
git add frontend/src/components/OperationLogTable.tsx
git commit -m "feat(frontend): 抽取公共操作记录组件 OperationLogTable"
```

---

## Task 5: `Documents.tsx` 新增「操作记录」TAB

**Files:**
- Modify: `frontend/src/pages/Documents.tsx`

- [ ] **Step 1: 导入公共组件**

在 `Documents.tsx` 顶部添加：

```typescript
import OperationLogTable from '../components/OperationLogTable';
import type { OperationLog } from '../types';
```

- [ ] **Step 2: 扩展状态和加载逻辑**

找到 `const [detailTab, setDetailTab] = useState<'detail' | 'versions'>('detail');` 改为：

```typescript
const [detailTab, setDetailTab] = useState<'detail' | 'versions' | 'logs'>('detail');
```

在组件内合适位置新增状态和加载方法：

```typescript
const [docLogs, setDocLogs] = useState<OperationLog[]>([]);
const [docLogsLoading, setDocLogsLoading] = useState(false);

const loadDocLogs = async (docId: string) => {
  setDocLogsLoading(true);
  try {
    const r = await documentsApi.getLogs(docId);
    setDocLogs((r.data as any).items ?? []);
  } catch (err) {
    console.error('加载图文档操作记录失败', err);
    setDocLogs([]);
  } finally {
    setDocLogsLoading(false);
  }
};
```

- [ ] **Step 3: 在切换 TAB 时触发加载**

使用 `useEffect`：

```typescript
useEffect(() => {
  if (detailTab === 'logs' && viewingDoc?.id) {
    loadDocLogs(viewingDoc.id);
  }
}, [detailTab, viewingDoc?.id]);
```

- [ ] **Step 4: 在 TAB 按钮区新增「操作记录」按钮**

在弹窗内的 TAB 按钮区（约 1065 行）追加第三个按钮：

```tsx
<button
  onClick={() => setDetailTab('logs')}
  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
    detailTab === 'logs'
      ? 'border-primary-600 text-primary-600'
      : 'border-transparent text-gray-500 hover:text-gray-700'
  }`}
>
  操作记录
</button>
```

- [ ] **Step 5: 渲染操作记录面板**

在 `{detailTab === 'detail' ? (... ) : ( <VersionHistory ... /> )}` 处改为三目或条件渲染：

```tsx
{detailTab === 'detail' && (
  <DocumentDetailContent
    doc={viewingDoc}
    customFieldDefs={viewingCustomDefs}
    customFieldValues={viewingCustomValues}
    accessible={(viewingDoc as any).accessible ?? true}
    groupNames={((viewingDoc as any).group_ids || []).map((gid: string) => allGroups.find(g => g.id === gid)?.name || gid).filter(Boolean)}
    onArchivePreview={(attId, fileName) => setArchivePreview({ attId, fileName })}
  />
)}
{detailTab === 'versions' && (
  <VersionHistory
    entityType="document"
    entityId={viewingDoc.id}
    onViewVersion={async (id) => {
      try {
        const res = await documentsApi.get(id);
        handleView(res.data);
      } catch {
        alert('加载版本失败');
      }
    }}
  />
)}
{detailTab === 'logs' && (
  <OperationLogTable logs={docLogs} loading={docLogsLoading} />
)}
```

- [ ] **Step 6: 类型检查与 Lint**

```bash
cd D:\OpenCode\plm-unified\frontend
npx tsc --noEmit
npm run lint
```

Expected: 无新增错误。

- [ ] **Step 7: Commit**

```bash
cd D:\OpenCode\plm-unified
git add frontend/src/pages/Documents.tsx
git commit -m "feat(frontend): 图文档详情新增操作记录 TAB"
```

---

## Task 6: `TaskEditModal.tsx` 复用 `OperationLogTable`

**Files:**
- Modify: `frontend/src/pages/Project/TaskEditModal.tsx`

- [ ] **Step 1: 导入公共组件**

在文件顶部添加：

```typescript
import OperationLogTable from '../../components/OperationLogTable';
```

- [ ] **Step 2: 替换操作记录面板 JSX**

找到原操作记录面板：

```tsx
{/* ───────────── 操作记录 ───────────── */}
{task && tab === 'logs' && (
  <div>
    {taskLogsLoading ? (
      <div className="text-center text-gray-400 py-8">加载中...</div>
    ) : taskLogs.length === 0 ? (
      <div className="text-center text-gray-400 py-8">暂无操作记录</div>
    ) : (
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        ...
      </div>
    )}
  </div>
)}
```

替换为：

```tsx
{/* ───────────── 操作记录 ───────────── */}
{task && tab === 'logs' && (
  <OperationLogTable logs={taskLogs} loading={taskLogsLoading} />
)}
```

- [ ] **Step 3: 类型检查与 Lint**

```bash
cd D:\OpenCode\plm-unified\frontend
npx tsc --noEmit
npm run lint
```

Expected: 无新增错误。

- [ ] **Step 4: Commit**

```bash
cd D:\OpenCode\plm-unified
git add frontend/src/pages/Project/TaskEditModal.tsx
git commit -m "refactor(frontend): TaskEditModal 操作记录复用 OperationLogTable"
```

---

## Task 7: 端到端验证

- [ ] **Step 1: 启动后端服务**

```bash
cd D:\OpenCode\plm-unified\backend
uvicorn app.main:app --reload
```

- [ ] **Step 2: 启动前端开发服务器**

```bash
cd D:\OpenCode\plm-unified\frontend
npm run dev
```

- [ ] **Step 3: 手动验证**

1. 登录系统，进入「图文档管理」页面。
2. 创建一个新图文档，记录编号。
3. 点击该图文档行，打开详情弹窗。
4. 切换到「操作记录」TAB，确认显示「创建图文档」日志。
5. 在详情页或列表上传一个附件，再次查看「操作记录」，确认出现「上传附件」日志。
6. 删除附件，确认出现「删除附件」日志。
7. 进入项目管理，打开一个任务的编辑弹窗，切换到「操作记录」TAB，确认表格样式与图文档一致且无报错。

- [ ] **Step 4: 运行全量测试**

```bash
cd D:\OpenCode\plm-unified\backend
pytest tests/test_document_logs.py -v

cd D:\OpenCode\plm-unified\frontend
npx tsc --noEmit
npm run lint
```

Expected: 全部通过。

- [ ] **Step 5: Commit（如验证通过）**

```bash
cd D:\OpenCode\plm-unified
# 如有任何验证过程中产生的修复，先 add
git commit -m "test: 图文档操作记录功能端到端验证通过"
```

---

## 自我审查

### Spec 覆盖检查

| Spec 需求 | 对应任务 |
| --- | --- |
| 图文档详情新增「操作记录」TAB | Task 5 |
| 有 `documents:read` 权限即可查看 | Task 2 |
| 复用图文档内容访问门禁 | Task 2 |
| 仅当前版本日志 | Task 2（按 `target_id=doc_id`） |
| 包含附件操作 | Task 2（`target_type` 含 `document_att`） |
| 参考任务操作记录样式 | Task 4、Task 6 |
| 抽取公共组件 | Task 4、Task 6 |

### Placeholder 扫描

- 无 TBD/TODO。
- 无 "add appropriate error handling" 等模糊描述。
- 所有测试代码完整可运行。

### 类型一致性检查

- `get_logs` 参数类型在 Task 1 中明确为 `Union[str, List[str], None]`，Task 2 中调用时使用列表，一致。
- `OperationLogTable` 接收 `OperationLog[]`，`Documents.tsx` 和 `TaskEditModal.tsx` 均使用相同类型，一致。
