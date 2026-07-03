# 图文档操作记录功能设计

## 1. 需求背景

图文档详情页当前仅有「基本信息」「版本历史」两个 TAB。为提升可追溯性，需要参照项目管理的「任务编辑弹窗-操作记录」TAB，在图文档详情弹窗中增加「操作记录」TAB，展示当前版本图文档及其附件的关键操作日志。

## 2. 设计决策

经讨论确认以下关键决策：

| 决策项 | 结论 |
| --- | --- |
| 查看权限 | 拥有 `documents:read` 权限且通过图文档内容访问门禁的用户即可查看 |
| 日志范围 | 仅当前版本（按当前 `doc_id` 过滤） |
| 日志内容 | 包含图文档主记录操作（`target_type=document`）和附件操作（`target_type=document_att`） |
| 实现方案 | 后端新增独立路由；前端抽取公共操作记录组件复用 |

## 3. 架构概述

在现有「图文档详情弹窗」中新增第三个 TAB「操作记录」，与「基本信息」「版本历史」并列。

- **后端**：在 `documents.py` 新增专用路由 `GET /documents/{doc_id}/logs`，权限使用 `documents:read`，并复用图文档内容访问门禁。查询范围限定在当前版本的 `doc_id`，同时返回 `target_type=document` 和 `target_type=document_att` 两类日志。
- **前端**：抽取公共组件 `OperationLogTable.tsx` 统一渲染操作记录表格；`Documents.tsx` 新增 `logs` TAB；`TaskEditModal.tsx` 的操作记录 TAB 改为复用该组件。
- **数据模型**：完全复用现有 `operation_logs` 表，不新增表/字段。

## 4. 后端设计

### 4.1 扩展通用日志查询 `app/crud/__init__.py`

将 `get_logs` 的 `target_type` 参数扩展为支持字符串或字符串列表，便于一次查询多种操作类型。

```python
def get_logs(db, skip=0, limit=100, target_type=None, target_id=None):
    """查询操作日志。target_type 支持单个字符串或字符串列表。"""
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

### 4.2 新增路由 `GET /documents/{doc_id}/logs`

在 `app/routers/documents.py` 新增如下路由：

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
    # 复用图文档内容访问门禁，保持与详情接口一致
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

### 4.3 权限与门禁

- 路由依赖 `require_permission("documents:read")`。
- 额外调用 `enforce_document_content_access`：即使拥有读权限，若图文档关联了用户组且当前用户不在组内、不是创建人、也不是 admin，则拒绝访问，与现有详情接口保持一致。

### 4.4 已有日志记录点

以下操作已写入 `target_type="document"` 或 `"document_att"`、`target_id=doc_id` 的日志，无需改动：

- 创建图文档
- 更新图文档
- 软删除图文档
- 图文档升版
- 上传附件
- 删除附件

## 5. 前端设计

### 5.1 抽取公共组件 `frontend/src/components/OperationLogTable.tsx`

该组件接收操作日志数组和加载状态，统一渲染表格。任务和图文档的操作记录 TAB 均复用此组件。

```typescript
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

### 5.2 `Documents.tsx` 调整

- 状态扩展：
  ```typescript
  const [detailTab, setDetailTab] = useState<'detail' | 'versions' | 'logs'>('detail');
  ```
- 新增状态和加载方法：
  ```typescript
  const [docLogs, setDocLogs] = useState<OperationLog[]>([]);
  const [docLogsLoading, setDocLogsLoading] = useState(false);

  const loadDocLogs = async (docId: string) => {
    setDocLogsLoading(true);
    try {
      const r = await documentsApi.getLogs(docId);
      setDocLogs((r.data as any).items ?? []);
    } catch {
      setDocLogs([]);
    } finally {
      setDocLogsLoading(false);
    }
  };
  ```
- 在 TAB 按钮区新增「操作记录」按钮。
- `detailTab === 'logs'` 时渲染：
  ```tsx
  <OperationLogTable logs={docLogs} loading={docLogsLoading} />
  ```
- 打开弹窗或切换图文档时重置 `detailTab` 为 `'detail'`（已有逻辑保持不变）。

### 5.3 `TaskEditModal.tsx` 调整

- 引入 `OperationLogTable`。
- 移除原内联的操作记录表格 JSX。
- `tab === 'logs'` 面板改为：
  ```tsx
  <OperationLogTable logs={taskLogs} loading={taskLogsLoading} />
  ```

### 5.4 API 层

在 `frontend/src/services/api.ts` 的 `documentsApi` 中新增：

```typescript
getLogs: (id: string) => api.get(`/documents/${id}/logs`),
```

## 6. 数据流

1. 用户在图文档列表点击某行 → `setViewingDoc(doc)`，弹窗打开，`detailTab` 默认为 `detail`。
2. 用户点击「操作记录」TAB → `setDetailTab('logs')`。
3. `useEffect` 检测到 `detailTab === 'logs'` → 调用 `documentsApi.getLogs(viewingDoc.id)`。
4. 后端校验 `documents:read` 权限和图文档内容访问门禁 → 查询 `operation_logs` 中 `target_id=doc_id` 且 `target_type in ('document', 'document_att')` 的记录。
5. 返回 `{items, total}`，前端渲染 `OperationLogTable`。

## 7. 测试策略

- **后端单元测试**：新增测试用例覆盖 `GET /documents/{doc_id}/logs` 的权限（无权限 403、无组权限 403）、无日志空返回、同时包含 `document` 和 `document_att` 日志。
- **前端组件测试**：验证 `OperationLogTable` 在 loading、空数据、有数据三种状态下的渲染。
- **集成测试**：创建图文档 → 更新 → 上传附件 → 删除附件 → 查看操作记录 TAB，确认日志按时间倒序展示。

## 8. 风险与回退

- `get_logs` 扩展参数类型后，需确认所有现有调用点（`/logs`、`/projects/{id}/tasks/{id}/logs`）行为不变。
- `OperationLogTable` 的 `ACTION_CLASS` 映射需要随新增 action 名称同步维护。
