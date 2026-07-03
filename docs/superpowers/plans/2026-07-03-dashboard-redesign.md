# 主页仪表盘重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将单调的主页仪表盘重构为"个人工作区 + 全局概览"两区融合、区内错落磁贴的面板。

**Architecture:** 前端把 `Dashboard.tsx` 拆分为 `pages/Dashboard/` 目录：纯数据逻辑集中在可单测的 `lib/aggregate.ts`（vitest TDD），数据获取封装在 `hooks.ts`，展示层拆成聚焦的磁贴组件，`index.tsx` 负责两区响应式网格布局。后端新增两个只读聚合接口 `GET /dashboard/my-todos`（ECR/ECO 待我审批 + 我发起被驳回）与 `GET /projects/my-tasks`（指派给我且未完成的任务），因列表 brief 不含评审人、且无跨项目任务接口。

**Tech Stack:** 前端 React 18 + TypeScript + Zustand + TailwindCSS + react-router v6 + Vitest。后端 FastAPI + SQLAlchemy + pytest（SQLite 内存库，crud 层测试）。

**参考 spec：** `docs/superpowers/specs/2026-07-03-dashboard-redesign-design.md`

---

## 文件结构

**前端（新增/修改）**
- 删除：`frontend/src/pages/Dashboard.tsx`
- 新建：`frontend/src/pages/Dashboard/index.tsx` — 布局composition（`App.tsx` 的 `import Dashboard from './pages/Dashboard'` 自动解析到本目录 index，无需改 App.tsx）
- 新建：`frontend/src/pages/Dashboard/lib/aggregate.ts` — 纯函数（问候、相对时间、状态分布、逾期天数、最近编辑去重、收藏展平、动态格式化）
- 新建：`frontend/src/pages/Dashboard/lib/aggregate.test.ts` — vitest 单测
- 新建：`frontend/src/pages/Dashboard/hooks.ts` — 数据获取 hooks
- 新建：`frontend/src/pages/Dashboard/tiles.tsx` — 展示型磁贴：`GreetingHeader`/`KpiStrip`/`StatusDistributionTile`/`RecentItemsTile`/`FavoritesTile`/`ActivityFeedTile` + 共享 `Tile`/`EmptyState`
- 新建：`frontend/src/pages/Dashboard/MyTodosTile.tsx` — 待我处理（主磁贴，自带 fetch）
- 新建：`frontend/src/pages/Dashboard/MyTasksTile.tsx` — 我的任务（自带 fetch）
- 修改：`frontend/src/services/api.ts` — 新增 `dashboardApi.getMyTodos`、`projectApi.myTasks`
- 修改：`frontend/src/types/index.ts` — 新增 `MyTodoItem`、`MyTaskItem` 类型

**后端（新增/修改）**
- 新建：`backend/app/crud/dashboard_todos.py` — `get_my_todos(db, user_id)`
- 新建：`backend/tests/test_dashboard_todos.py`
- 修改：`backend/app/routers/dashboard.py` — 新增 `GET /my-todos` 路由
- 新建：`backend/app/crud/dashboard_mytasks.py` — `get_my_tasks(db, user_id)`
- 新建：`backend/tests/test_dashboard_mytasks.py`
- 修改：`backend/app/routers/projects.py` — 新增 `GET /my-tasks` 路由（必须声明在 `@router.get("/{project_id}")` 之前）

**测试约定：** 前端纯逻辑用 vitest 单测（`npx vitest run <file>`，工作目录 `frontend/`）；React 组件仓库无 RTL，用 preview 目视验证，不写组件单测。后端聚合逻辑在 crud 层用 pytest + `db` fixture 单测（`pytest tests/<file> -v`，工作目录 `backend/`）。

---

## Phase A — 前端布局 + 零后端磁贴

本阶段交付完整两区布局与 6 个可用磁贴（问候/KPI/状态分布/最近编辑/收藏/动态流）。`MyTodosTile`/`MyTasksTile` 在本阶段先渲染磁贴外壳 + 空态（其接口在 Phase B/C 接入）。

### Task A1: 纯函数 — 问候与相对时间

**Files:**
- Create: `frontend/src/pages/Dashboard/lib/aggregate.ts`
- Test: `frontend/src/pages/Dashboard/lib/aggregate.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
import { describe, it, expect } from 'vitest';
import { greeting, relativeTime } from './aggregate';

describe('greeting', () => {
  it('按小时返回问候语', () => {
    expect(greeting(8)).toBe('早上好');
    expect(greeting(14)).toBe('下午好');
    expect(greeting(21)).toBe('晚上好');
    expect(greeting(0)).toBe('晚上好');
  });
});

describe('relativeTime', () => {
  const now = Date.parse('2026-07-03T12:00:00Z');
  it('分钟/小时/天', () => {
    expect(relativeTime('2026-07-03T11:58:00Z', now)).toBe('2分钟前');
    expect(relativeTime('2026-07-03T09:00:00Z', now)).toBe('3小时前');
    expect(relativeTime('2026-07-01T12:00:00Z', now)).toBe('2天前');
  });
  it('刚刚 / 空值', () => {
    expect(relativeTime('2026-07-03T11:59:30Z', now)).toBe('刚刚');
    expect(relativeTime('', now)).toBe('');
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run src/pages/Dashboard/lib/aggregate.test.ts`
Expected: FAIL（模块/导出不存在）

- [ ] **Step 3: 实现**

```typescript
export function greeting(hour: number): string {
  if (hour >= 5 && hour < 12) return '早上好';
  if (hour >= 12 && hour < 18) return '下午好';
  return '晚上好';
}

export function relativeTime(iso: string, nowMs: number): string {
  if (!iso) return '';
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return '';
  const diff = Math.floor((nowMs - t) / 1000);
  if (diff < 60) return '刚刚';
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
  return `${Math.floor(diff / 86400)}天前`;
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run src/pages/Dashboard/lib/aggregate.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/Dashboard/lib/aggregate.ts frontend/src/pages/Dashboard/lib/aggregate.test.ts
git commit -m "feat(dashboard): 问候与相对时间纯函数"
```

### Task A2: 纯函数 — 状态分布与逾期天数

**Files:**
- Modify: `frontend/src/pages/Dashboard/lib/aggregate.ts`
- Test: `frontend/src/pages/Dashboard/lib/aggregate.test.ts`

- [ ] **Step 1: 追加失败测试**

```typescript
import { statusDistribution, overdueDays } from './aggregate';

describe('statusDistribution', () => {
  it('计数并给出百分比', () => {
    const items = [
      { status: 'draft' }, { status: 'released' }, { status: 'released' },
      { status: 'frozen' }, { status: 'obsolete' },
    ];
    const d = statusDistribution(items);
    expect(d.total).toBe(5);
    expect(d.released).toBe(2);
    expect(d.pct.released).toBe(40);
    expect(d.pct.draft).toBe(20);
  });
  it('空数组不除零', () => {
    const d = statusDistribution([]);
    expect(d.total).toBe(0);
    expect(d.pct.released).toBe(0);
  });
});

describe('overdueDays', () => {
  const now = Date.parse('2026-07-03T12:00:00Z');
  it('过期返回正天数，未过期返回 0', () => {
    expect(overdueDays('2026-06-30', now)).toBe(3);
    expect(overdueDays('2026-07-10', now)).toBe(0);
    expect(overdueDays(null, now)).toBe(0);
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run src/pages/Dashboard/lib/aggregate.test.ts`
Expected: FAIL

- [ ] **Step 3: 实现（追加到 aggregate.ts）**

```typescript
export type StatusKey = 'draft' | 'frozen' | 'released' | 'obsolete';
export interface Distribution {
  total: number;
  draft: number; frozen: number; released: number; obsolete: number;
  pct: Record<StatusKey, number>;
}

export function statusDistribution(items: { status: string }[]): Distribution {
  const d: Distribution = {
    total: 0, draft: 0, frozen: 0, released: 0, obsolete: 0,
    pct: { draft: 0, frozen: 0, released: 0, obsolete: 0 },
  };
  for (const it of items) {
    d.total++;
    if (it.status === 'draft' || it.status === 'frozen' || it.status === 'released' || it.status === 'obsolete') {
      d[it.status]++;
    }
  }
  if (d.total > 0) {
    (['draft', 'frozen', 'released', 'obsolete'] as StatusKey[]).forEach((k) => {
      d.pct[k] = Math.round((d[k] / d.total) * 100);
    });
  }
  return d;
}

export function overdueDays(plannedEnd: string | null, nowMs: number): number {
  if (!plannedEnd) return 0;
  const t = Date.parse(plannedEnd);
  if (Number.isNaN(t)) return 0;
  const diff = Math.floor((nowMs - t) / 86400000);
  return diff > 0 ? diff : 0;
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run src/pages/Dashboard/lib/aggregate.test.ts`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/Dashboard/lib/aggregate.ts frontend/src/pages/Dashboard/lib/aggregate.test.ts
git commit -m "feat(dashboard): 状态分布与逾期天数纯函数"
```

### Task A3: 纯函数 — 最近编辑去重、收藏展平、动态格式化

**Files:**
- Modify: `frontend/src/pages/Dashboard/lib/aggregate.ts`
- Test: `frontend/src/pages/Dashboard/lib/aggregate.test.ts`

- [ ] **Step 1: 追加失败测试**

```typescript
import { dedupeRecentRefs, flattenFavorites, formatActivity } from './aggregate';

describe('dedupeRecentRefs', () => {
  it('按 target 去重保留最新，仅保留实体类型，限量', () => {
    const logs = [
      { target_type: 'part', target_id: 'p1', action: 'update', created_at: '2026-07-03T10:00:00Z' },
      { target_type: 'part', target_id: 'p1', action: 'update', created_at: '2026-07-03T09:00:00Z' },
      { target_type: 'document', target_id: 'd1', action: 'create', created_at: '2026-07-03T08:00:00Z' },
      { target_type: 'user', target_id: 'u1', action: 'update', created_at: '2026-07-03T11:00:00Z' },
    ] as any;
    const refs = dedupeRecentRefs(logs, 5);
    expect(refs.map((r) => r.targetId)).toEqual(['p1', 'd1']);
    expect(refs[0].at).toBe('2026-07-03T10:00:00Z');
  });
});

describe('flattenFavorites', () => {
  it('递归展平文件夹树的 items 并限量', () => {
    const resp = { folders: [
      { items: [{ id: 'i1', entity_type: 'part', entity_id: 'p1', code: 'P-1', name: '零件一' }],
        children: [{ items: [{ id: 'i2', entity_type: 'document', entity_id: 'd1', code: 'D-1', name: '文档一' }], children: [] }] },
    ] };
    const favs = flattenFavorites(resp, 10);
    expect(favs.map((f) => f.code)).toEqual(['P-1', 'D-1']);
  });
});

describe('formatActivity', () => {
  it('组合动作与对象为可读句', () => {
    const log = { username: '张三', action: 'update', target_type: 'part', target_id: 'p1', detail: 'P-0148', created_at: '2026-07-03T11:50:00Z' } as any;
    const a = formatActivity(log, Date.parse('2026-07-03T12:00:00Z'));
    expect(a.text).toBe('张三 更新了零件');
    expect(a.time).toBe('10分钟前');
    expect(a.initial).toBe('张');
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && npx vitest run src/pages/Dashboard/lib/aggregate.test.ts`
Expected: FAIL

- [ ] **Step 3: 实现（追加到 aggregate.ts）**

```typescript
const ENTITY_TYPES = new Set(['part', 'assembly', 'document', 'configuration']);
const ENTITY_LABEL: Record<string, string> = { part: '零件', assembly: '部件', document: '图文档', configuration: '构型项' };
const ACTION_LABEL: Record<string, string> = { create: '创建了', update: '更新了', delete: '删除了', login: '登录', review: '审批了' };

export interface RecentRef { targetType: string; targetId: string; at: string; }

export function dedupeRecentRefs(
  logs: { target_type: string; target_id: string; created_at: string }[],
  limit: number,
): RecentRef[] {
  const seen = new Set<string>();
  const out: RecentRef[] = [];
  for (const l of logs) {
    if (!ENTITY_TYPES.has(l.target_type)) continue;
    const key = `${l.target_type}:${l.target_id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ targetType: l.target_type, targetId: l.target_id, at: l.created_at });
    if (out.length >= limit) break;
  }
  return out;
}

export interface FavItem { id: string; entity_type: string; entity_id: string; code: string; name: string; }

export function flattenFavorites(resp: any, limit: number): FavItem[] {
  const out: FavItem[] = [];
  const walk = (folders: any[]) => {
    for (const f of folders || []) {
      for (const it of f.items || []) {
        out.push(it);
        if (out.length >= limit) return;
      }
      walk(f.children || []);
      if (out.length >= limit) return;
    }
  };
  walk(resp?.folders || []);
  return out.slice(0, limit);
}

export interface Activity { initial: string; text: string; time: string; targetType: string; targetId: string; }

export function formatActivity(
  log: { username: string; action: string; target_type: string; target_id: string; created_at: string },
  nowMs: number,
): Activity {
  const action = ACTION_LABEL[log.action] || log.action;
  const label = ENTITY_LABEL[log.target_type] || log.target_type;
  return {
    initial: (log.username || '?').charAt(0),
    text: `${log.username} ${action}${label}`,
    time: relativeTime(log.created_at, nowMs),
    targetType: log.target_type,
    targetId: log.target_id,
  };
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && npx vitest run src/pages/Dashboard/lib/aggregate.test.ts`
Expected: PASS（全部 aggregate 测试）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/Dashboard/lib/aggregate.ts frontend/src/pages/Dashboard/lib/aggregate.test.ts
git commit -m "feat(dashboard): 最近编辑去重、收藏展平、动态格式化纯函数"
```

### Task A4: 数据获取 hooks

**Files:**
- Create: `frontend/src/pages/Dashboard/hooks.ts`

- [ ] **Step 1: 实现 hooks**

```typescript
import { useEffect, useState } from 'react';
import { usersApi, logsApi, boardApi } from '../../services/api';
import { useDataStore } from '../../stores/data';
import type { User } from '../../types';
import { dedupeRecentRefs, flattenFavorites, formatActivity, type Activity, type FavItem } from './lib/aggregate';

export function useUserList(): User[] {
  const [users, setUsers] = useState<User[]>([]);
  useEffect(() => {
    let cancelled = false;
    usersApi.list({ page_size: 10000 })
      .then((res) => { if (!cancelled) { const d = res.data; setUsers(Array.isArray(d) ? d : (d?.items ?? [])); } })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);
  return users;
}

export interface RecentDisplay { key: string; entityType: string; entityId: string; code: string; name: string; }

export function useRecentEdited(userId: string | undefined, limit = 5): RecentDisplay[] {
  const parts = useDataStore((s) => s.parts);
  const assemblies = useDataStore((s) => s.assemblies);
  const documents = useDataStore((s) => s.documents);
  const configItems = useDataStore((s) => s.configItems);
  const [refs, setRefs] = useState<{ targetType: string; targetId: string }[]>([]);
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    logsApi.list({ user_id: userId, limit: 60 })
      .then((res) => {
        const logs = res.data?.items ?? res.data ?? [];
        if (!cancelled) setRefs(dedupeRecentRefs(logs, limit));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [userId, limit]);
  const byId = new Map<string, { code: string; name: string }>();
  parts.forEach((p) => byId.set(`part:${p.id}`, { code: (p as any).number ?? '', name: p.name }));
  assemblies.forEach((a) => byId.set(`assembly:${a.id}`, { code: (a as any).number ?? '', name: a.name }));
  documents.forEach((d) => byId.set(`document:${d.id}`, { code: (d as any).code ?? '', name: d.name }));
  configItems.forEach((c) => byId.set(`configuration:${c.id}`, { code: c.code, name: c.name }));
  return refs
    .map((r) => {
      const hit = byId.get(`${r.targetType}:${r.targetId}`);
      return hit ? { key: `${r.targetType}:${r.targetId}`, entityType: r.targetType, entityId: r.targetId, code: hit.code, name: hit.name } : null;
    })
    .filter((x): x is RecentDisplay => x !== null);
}

export function useFavorites(limit = 6): FavItem[] {
  const [favs, setFavs] = useState<FavItem[]>([]);
  useEffect(() => {
    let cancelled = false;
    boardApi.getDashboard()
      .then((res) => { if (!cancelled) setFavs(flattenFavorites(res.data, limit)); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [limit]);
  return favs;
}

export function useActivityFeed(limit = 6): Activity[] {
  const [acts, setActs] = useState<Activity[]>([]);
  useEffect(() => {
    let cancelled = false;
    logsApi.list({ limit })
      .then((res) => {
        const logs = res.data?.items ?? res.data ?? [];
        const now = Date.now();
        if (!cancelled) setActs(logs.map((l: any) => formatActivity(l, now)));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [limit]);
  return acts;
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无报错（若 `PartBrief` 无 `number` 字段，`(p as any)` 已兜底）

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/Dashboard/hooks.ts
git commit -m "feat(dashboard): 数据获取 hooks（最近编辑/收藏/动态流）"
```

### Task A5: 展示型磁贴组件（tiles.tsx）

**Files:**
- Create: `frontend/src/pages/Dashboard/tiles.tsx`

- [ ] **Step 1: 实现共享外壳 + 6 个磁贴**

```tsx
import { Link } from 'react-router-dom';
import { greeting, statusDistribution, type Distribution } from './lib/aggregate';
import type { RecentDisplay, Activity } from './hooks';
import type { FavItem } from './lib/aggregate';
import type { PartBrief, AssemblyBrief, DocumentBrief } from '../../types';

const ENTITY_ICON: Record<string, string> = { part: '🔧', assembly: '📦', document: '📄', configuration: '⚙️' };
const ENTITY_ROUTE: Record<string, string> = { part: '/parts', assembly: '/components', document: '/documents', configuration: '/configurations' };

export function Tile({ title, icon, right, children, className = '' }: {
  title: string; icon?: React.ReactNode; right?: React.ReactNode; children: React.ReactNode; className?: string;
}) {
  return (
    <div className={`bg-white rounded-xl border border-gray-200 p-4 flex flex-col ${className}`}>
      <div className="flex items-center gap-2 mb-3">
        {icon && <span className="text-gray-400">{icon}</span>}
        <h3 className="text-sm font-medium text-gray-800">{title}</h3>
        {right && <span className="ml-auto">{right}</span>}
      </div>
      {children}
    </div>
  );
}

export function EmptyState({ text }: { text: string }) {
  return <div className="flex-1 flex items-center justify-center text-xs text-gray-400 py-4">{text}</div>;
}

export function GreetingHeader({ name, todoCount, overdueCount }: { name: string; todoCount: number; overdueCount: number }) {
  const hour = new Date().getHours();
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-base font-medium text-gray-900">{greeting(hour)}，{name || '同事'}</span>
      <span className="text-xs text-gray-400">· 你有 {todoCount} 项待处理{overdueCount > 0 ? `、${overdueCount} 个任务逾期` : ''}</span>
    </div>
  );
}

export function KpiStrip({ parts, assemblies, documents, changeOpen }: {
  parts: number; assemblies: number; documents: number; changeOpen: number;
}) {
  const items = [
    { label: '零件', value: parts, cls: 'text-gray-900', to: '/parts' },
    { label: '部件', value: assemblies, cls: 'text-gray-900', to: '/components' },
    { label: '图文档', value: documents, cls: 'text-gray-900', to: '/documents' },
    { label: '变更进行中', value: changeOpen, cls: 'text-red-500', to: '/ecr' },
  ];
  return (
    <div className="grid grid-cols-4 gap-3">
      {items.map((it) => (
        <Link key={it.label} to={it.to} className="bg-gray-50 rounded-xl p-3 flex flex-col items-center hover:bg-gray-100 transition-colors">
          <span className={`text-xl font-medium ${it.cls}`}>{it.value}</span>
          <span className="text-xs text-gray-500 mt-1">{it.label}</span>
        </Link>
      ))}
    </div>
  );
}

const SEG_COLOR: Record<string, string> = { draft: '#85B7EB', frozen: '#EF9F27', released: '#97C459', obsolete: '#F09595' };
const SEG_LABEL: Record<string, string> = { draft: '草稿', frozen: '冻结', released: '发布', obsolete: '作废' };

function DistRow({ label, dist }: { label: string; dist: Distribution }) {
  const keys: ('draft' | 'frozen' | 'released' | 'obsolete')[] = ['draft', 'frozen', 'released', 'obsolete'];
  return (
    <div>
      <div className="text-xs text-gray-500 mb-1">{label} · {dist.total}</div>
      <div className="flex h-3 rounded overflow-hidden bg-gray-100">
        {dist.total > 0 && keys.map((k) => dist.pct[k] > 0 && (
          <div key={k} style={{ width: `${dist.pct[k]}%`, background: SEG_COLOR[k] }} title={`${SEG_LABEL[k]} ${dist[k]}`} />
        ))}
      </div>
    </div>
  );
}

export function StatusDistributionTile({ parts, assemblies, documents }: {
  parts: PartBrief[]; assemblies: AssemblyBrief[]; documents: DocumentBrief[];
}) {
  const rows = [
    { label: '零件', dist: statusDistribution(parts) },
    { label: '部件', dist: statusDistribution(assemblies) },
    { label: '图文档', dist: statusDistribution(documents) },
  ];
  const empty = rows.every((r) => r.dist.total === 0);
  return (
    <Tile title="状态分布" icon={<span>📊</span>} className="min-h-[180px]">
      {empty ? <EmptyState text="暂无数据，去各页面检出后自动统计" /> : (
        <div className="flex flex-col gap-3 flex-1">
          {rows.map((r) => <DistRow key={r.label} label={r.label} dist={r.dist} />)}
          <div className="flex gap-3 flex-wrap text-xs text-gray-500 mt-auto pt-1">
            {(['draft', 'frozen', 'released', 'obsolete'] as const).map((k) => (
              <span key={k} className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-sm inline-block" style={{ background: SEG_COLOR[k] }} />{SEG_LABEL[k]}
              </span>
            ))}
          </div>
        </div>
      )}
    </Tile>
  );
}

export function RecentItemsTile({ items }: { items: RecentDisplay[] }) {
  return (
    <Tile title="最近访问" icon={<span>🕘</span>}>
      {items.length === 0 ? <EmptyState text="最近没有编辑记录" /> : (
        <div className="flex flex-col gap-2">
          {items.map((it) => (
            <Link key={it.key} to={ENTITY_ROUTE[it.entityType] || '/'} className="flex items-center gap-2 text-xs text-gray-700 hover:text-blue-600 truncate">
              <span>{ENTITY_ICON[it.entityType]}</span>
              <span className="text-gray-400">{it.code}</span>
              <span className="truncate">{it.name}</span>
            </Link>
          ))}
        </div>
      )}
    </Tile>
  );
}

export function FavoritesTile({ items }: { items: FavItem[] }) {
  return (
    <Tile title="我的收藏" icon={<span className="text-amber-500">★</span>}>
      {items.length === 0 ? <EmptyState text="还没有收藏，去看板添加" /> : (
        <div className="flex flex-col gap-2">
          {items.map((it) => (
            <Link key={it.id} to={ENTITY_ROUTE[it.entity_type] || '/'} className="flex items-center gap-2 text-xs text-gray-700 hover:text-blue-600 truncate">
              <span>{ENTITY_ICON[it.entity_type]}</span>
              <span className="text-gray-400">{it.code}</span>
              <span className="truncate">{it.name}</span>
            </Link>
          ))}
        </div>
      )}
    </Tile>
  );
}

export function ActivityFeedTile({ items }: { items: Activity[] }) {
  return (
    <Tile title="系统动态流" icon={<span>📡</span>} className="min-h-[180px]">
      {items.length === 0 ? <EmptyState text="暂无动态" /> : (
        <div className="flex flex-col gap-3">
          {items.map((a, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-full bg-blue-50 text-blue-600 text-xs flex items-center justify-center shrink-0">{a.initial}</span>
              <span className="flex-1 text-xs text-gray-700 truncate">{a.text}</span>
              <span className="text-xs text-gray-400 shrink-0">{a.time}</span>
            </div>
          ))}
        </div>
      )}
    </Tile>
  );
}
```

- [ ] **Step 2: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无报错

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/Dashboard/tiles.tsx
git commit -m "feat(dashboard): 展示型磁贴组件（问候/KPI/状态分布/最近/收藏/动态流）"
```

### Task A6: 待我处理 / 我的任务 磁贴外壳（先空态）

本任务先建两个磁贴的外壳与空态，接口在 Phase B/C 接入。

**Files:**
- Create: `frontend/src/pages/Dashboard/MyTodosTile.tsx`
- Create: `frontend/src/pages/Dashboard/MyTasksTile.tsx`

- [ ] **Step 1: MyTodosTile.tsx（占位空态版）**

```tsx
import { Tile, EmptyState } from './tiles';

export function MyTodosTile() {
  return (
    <Tile title="待我处理" icon={<span>📥</span>} right={<span className="text-xs text-gray-400">—</span>} className="min-h-[220px]">
      <EmptyState text="✅ 暂无待办" />
    </Tile>
  );
}
```

- [ ] **Step 2: MyTasksTile.tsx（占位空态版）**

```tsx
import { Tile, EmptyState } from './tiles';

export function MyTasksTile() {
  return (
    <Tile title="我的任务" icon={<span>✅</span>}>
      <EmptyState text="暂无指派给你的任务" />
    </Tile>
  );
}
```

- [ ] **Step 3: 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无报错

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/Dashboard/MyTodosTile.tsx frontend/src/pages/Dashboard/MyTasksTile.tsx
git commit -m "feat(dashboard): 待我处理/我的任务磁贴外壳"
```

### Task A7: 布局组装 index.tsx（替换旧 Dashboard.tsx）

**Files:**
- Create: `frontend/src/pages/Dashboard/index.tsx`
- Delete: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: 实现 index.tsx**

```tsx
import { useMemo } from 'react';
import { useDataStore } from '../../stores/data';
import { useAuthStore } from '../../stores/auth';
import { useRecentEdited, useFavorites, useActivityFeed } from './hooks';
import {
  GreetingHeader, KpiStrip, StatusDistributionTile, RecentItemsTile, FavoritesTile, ActivityFeedTile,
} from './tiles';
import { MyTodosTile } from './MyTodosTile';
import { MyTasksTile } from './MyTasksTile';

export default function Dashboard() {
  const parts = useDataStore((s) => s.parts);
  const assemblies = useDataStore((s) => s.assemblies);
  const documents = useDataStore((s) => s.documents);
  const user = useAuthStore((s) => s.user);

  const recent = useRecentEdited(user?.id, 5);
  const favorites = useFavorites(6);
  const activity = useActivityFeed(6);

  const changeOpen = 0; // Phase B 接入 my-todos 后由待办计数替换
  const hasData = parts.length > 0 || assemblies.length > 0 || documents.length > 0;

  const kpi = useMemo(() => ({
    parts: parts.length, assemblies: assemblies.length, documents: documents.length,
  }), [parts, assemblies, documents]);

  return (
    <div className="flex flex-col gap-4">
      <GreetingHeader name={user?.real_name || ''} todoCount={0} overdueCount={0} />

      {!hasData && (
        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-700 text-xs">
          当前无本地缓存数据，请先在对应页面检出。统计将自动从本地缓存计算。
        </div>
      )}

      {/* 个人工作区 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <MyTodosTile />
        <div className="flex flex-col gap-4">
          <MyTasksTile />
          <div className="grid grid-cols-2 gap-4">
            <RecentItemsTile items={recent} />
            <FavoritesTile items={favorites} />
          </div>
        </div>
      </div>

      <div className="border-t border-gray-200" />

      {/* 全局概览 */}
      <KpiStrip parts={kpi.parts} assemblies={kpi.assemblies} documents={kpi.documents} changeOpen={changeOpen} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <StatusDistributionTile parts={parts} assemblies={assemblies} documents={documents} />
        <ActivityFeedTile items={activity} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 删除旧文件**

```bash
git rm frontend/src/pages/Dashboard.tsx
```

- [ ] **Step 3: 类型检查 + 构建**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无报错（确认 `App.tsx` 的 `import Dashboard from './pages/Dashboard'` 解析到新目录）

- [ ] **Step 4: preview 目视验证**

用 preview 启动前端，登录后进入首页，确认：两区布局呈现、KPI/状态分布/最近/收藏/动态流磁贴各就位、空态文案正常、窄屏（resize mobile）个人区塌为单列、全局区磁贴各自全宽。修 console 报错。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/Dashboard/index.tsx
git commit -m "feat(dashboard): 两区错落磁贴布局组装，替换旧仪表盘"
```

---

## Phase B — 后端 my-todos 接口 + 待我处理磁贴

### Task B1: 后端 crud `get_my_todos`（TDD）

**Files:**
- Create: `backend/app/crud/dashboard_todos.py`
- Test: `backend/tests/test_dashboard_todos.py`

- [ ] **Step 1: 写失败测试**

```python
import uuid
import pytest
from app.crud.dashboard_todos import get_my_todos
from app.models.models_ecr import ECR, ECRReviewRecord
from app.models.models_eco import ECO


@pytest.fixture
def me():
    return uuid.uuid4()


def _ecr(**kw):
    d = dict(id=uuid.uuid4(), ecr_number="ECR-1", title="改规格", reason="x",
             priority="high", status="reviewing", reviewers=[], creator_id=uuid.uuid4())
    d.update(kw)
    return ECR(**d)


def test_ecr_pending_my_review_included(db, me):
    ecr = _ecr(reviewers=[{"user_id": str(me), "user_name": "我", "role": "r", "seq": 1}])
    db.add(ecr); db.commit()
    todos = get_my_todos(db, me)
    assert len(todos) == 1
    assert todos[0]["type"] == "ecr"
    assert todos[0]["kind"] == "review"
    assert todos[0]["number"] == "ECR-1"


def test_ecr_already_reviewed_excluded(db, me):
    ecr = _ecr(reviewers=[{"user_id": str(me), "seq": 1}])
    db.add(ecr); db.commit()
    db.add(ECRReviewRecord(ecr_id=ecr.id, reviewer_id=me, decision="approved")); db.commit()
    assert get_my_todos(db, me) == []


def test_my_rejected_ecr_included(db, me):
    ecr = _ecr(status="rejected", creator_id=me, reviewers=[])
    db.add(ecr); db.commit()
    todos = get_my_todos(db, me)
    assert len(todos) == 1
    assert todos[0]["kind"] == "rejected"


def test_not_reviewing_not_mine_excluded(db, me):
    db.add(_ecr(status="reviewing", reviewers=[{"user_id": str(uuid.uuid4())}])); db.commit()
    assert get_my_todos(db, me) == []
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_dashboard_todos.py -v`
Expected: FAIL（`app.crud.dashboard_todos` 不存在）

- [ ] **Step 3: 实现**

```python
"""待我处理聚合：ECR/ECO 待我审批 + 我发起被驳回。只读，不写日志。"""
from sqlalchemy.orm import Session
from app.models.models_ecr import ECR, ECRReviewRecord
from app.models.models_eco import ECO, ECOReviewRecord


def _is_reviewer(reviewers, user_id_str):
    for r in reviewers or []:
        if str(r.get("user_id")) == user_id_str:
            return True
    return False


def _collect(db: Session, user_id, Model, RecordModel, type_name, number_attr):
    uid = str(user_id)
    out = []
    reviewing = db.query(Model).filter(Model.status == "reviewing", Model.deleted_at.is_(None)).all()
    for m in reviewing:
        if not _is_reviewer(m.reviewers, uid):
            continue
        done = db.query(RecordModel).filter(
            RecordModel.__table__.c.get(f"{type_name}_id") == m.id,
            RecordModel.reviewer_id == user_id,
        ).first()
        if done:
            continue
        out.append(_row(m, type_name, number_attr, "review"))
    rejected = db.query(Model).filter(
        Model.status == "rejected", Model.creator_id == user_id, Model.deleted_at.is_(None)
    ).all()
    for m in rejected:
        out.append(_row(m, type_name, number_attr, "rejected"))
    return out


def _row(m, type_name, number_attr, kind):
    return {
        "type": type_name,
        "kind": kind,
        "id": str(m.id),
        "number": getattr(m, number_attr),
        "title": m.title,
        "priority": m.priority,
        "status": m.status,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def get_my_todos(db: Session, user_id):
    todos = []
    todos += _collect(db, user_id, ECR, ECRReviewRecord, "ecr", "ecr_number")
    todos += _collect(db, user_id, ECO, ECOReviewRecord, "eco", "eco_number")
    todos.sort(key=lambda x: x["updated_at"] or "", reverse=True)
    return todos
```

> 注：`RecordModel.__table__.c.get(...)` 用于统一取 `ecr_id`/`eco_id` 外键列。若可读性更好，可在 `_collect` 直接传入外键列参数 `fk_col`（如 `ECRReviewRecord.ecr_id`）替代。实现时二选一，保持一处清晰即可。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && pytest tests/test_dashboard_todos.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/crud/dashboard_todos.py backend/tests/test_dashboard_todos.py
git commit -m "feat(dashboard): get_my_todos 聚合 ECR/ECO 待办（crud + 测试）"
```

### Task B2: 后端路由 `GET /dashboard/my-todos`

**Files:**
- Modify: `backend/app/routers/dashboard.py`

- [ ] **Step 1: 顶部 import 追加**

在 `from app.crud import create_log` 下追加：

```python
from app.crud.dashboard_todos import get_my_todos
```

- [ ] **Step 2: 在 `# ===== 看板 =====` 注释上方新增路由**

```python
@router.get("/my-todos")
async def my_todos(db: Session = Depends(get_db), current_user: User = Depends(require_permission("dashboard:read"))):
    return {"items": get_my_todos(db, current_user.id)}
```

- [ ] **Step 3: 冒烟（应用可导入）**

Run: `cd backend && python -c "from app.routers.dashboard import router; print([r.path for r in router.routes if 'my-todos' in r.path])"`
Expected: 输出包含 `/dashboard/my-todos`

- [ ] **Step 4: 提交**

```bash
git add backend/app/routers/dashboard.py
git commit -m "feat(dashboard): 新增 GET /dashboard/my-todos 路由"
```

### Task B3: 前端接入待我处理

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/pages/Dashboard/MyTodosTile.tsx`
- Modify: `frontend/src/pages/Dashboard/index.tsx`

- [ ] **Step 1: 类型（types/index.ts 末尾追加）**

```typescript
export interface MyTodoItem {
  type: 'ecr' | 'eco';
  kind: 'review' | 'rejected';
  id: string;
  number: string;
  title: string;
  priority: string;
  status: string;
  updated_at: string | null;
}
```

- [ ] **Step 2: api（dashboardApi 内追加方法）**

将 `export const dashboardApi = { getStats: () => api.get('/dashboard/stats') };` 改为：

```typescript
export const dashboardApi = {
  getStats: () => api.get('/dashboard/stats'),
  getMyTodos: () => api.get('/dashboard/my-todos'),
};
```

- [ ] **Step 3: MyTodosTile.tsx 完整实现**

```tsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Tile, EmptyState } from './tiles';
import { dashboardApi } from '../../services/api';
import { relativeTime } from './lib/aggregate';
import type { MyTodoItem } from '../../types';

const TYPE_TAG: Record<string, { label: string; cls: string }> = {
  ecr: { label: 'ECR', cls: 'bg-blue-50 text-blue-800' },
  eco: { label: 'ECO', cls: 'bg-amber-50 text-amber-800' },
};
const PRIO_DOT: Record<string, string> = { urgent: '#E24B4A', high: '#EF9F27', normal: '#378ADD', low: '#888780' };
const TYPE_ROUTE: Record<string, string> = { ecr: '/ecr', eco: '/eco' };

export function MyTodosTile({ onCount }: { onCount?: (n: number) => void }) {
  const [items, setItems] = useState<MyTodoItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let cancelled = false;
    dashboardApi.getMyTodos()
      .then((res) => { if (!cancelled) { const list = res.data?.items ?? []; setItems(list); onCount?.(list.length); } })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoaded(true); });
    return () => { cancelled = true; };
  }, [onCount]);

  const now = Date.now();
  return (
    <Tile
      title="待我处理"
      icon={<span>📥</span>}
      right={items.length > 0 ? <span className="bg-red-50 text-red-600 text-xs px-2 py-0.5 rounded-full">{items.length}</span> : undefined}
      className="min-h-[220px]"
    >
      {loaded && items.length === 0 ? <EmptyState text="✅ 暂无待办" /> : (
        <div className="flex flex-col gap-2.5 flex-1">
          {items.slice(0, 5).map((it) => (
            <Link key={`${it.type}:${it.id}`} to={TYPE_ROUTE[it.type] || '/'} className="flex items-center gap-2 text-sm hover:bg-gray-50 rounded px-1 py-0.5">
              <span className={`text-xs px-1.5 rounded ${TYPE_TAG[it.type]?.cls || 'bg-gray-100 text-gray-700'}`}>{TYPE_TAG[it.type]?.label || it.type}</span>
              <span className={`truncate flex-1 ${it.kind === 'rejected' ? 'text-red-600' : 'text-gray-700'}`}>
                {it.title}{it.kind === 'rejected' ? ' · 被驳回' : ''}
              </span>
              {it.kind === 'review' && <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: PRIO_DOT[it.priority] || '#888' }} />}
              <span className="text-xs text-gray-400 shrink-0">{relativeTime(it.updated_at || '', now)}</span>
            </Link>
          ))}
          {items.length > 5 && <Link to="/ecr" className="text-xs text-blue-600 mt-auto">查看全部 {items.length} 项 →</Link>}
        </div>
      )}
    </Tile>
  );
}
```

- [ ] **Step 4: index.tsx 接入待办计数**

在 `Dashboard` 组件中新增 state 并传入：

```tsx
// 顶部 import useState
import { useMemo, useState } from 'react';
// 组件内：
const [todoCount, setTodoCount] = useState(0);
// JSX：<MyTodosTile onCount={setTodoCount} />
// GreetingHeader 改为：<GreetingHeader name={user?.real_name || ''} todoCount={todoCount} overdueCount={overdueCount} />
```

- [ ] **Step 5: 类型检查 + preview 验证**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无报错

preview：以有待审 ECR/ECO 的用户登录，确认待我处理磁贴列出条目、徽标数字、优先级点、被驳回红字、问候语待办数联动；无待办用户显示"✅ 暂无待办"。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/services/api.ts frontend/src/types/index.ts frontend/src/pages/Dashboard/MyTodosTile.tsx frontend/src/pages/Dashboard/index.tsx
git commit -m "feat(dashboard): 待我处理磁贴接入 my-todos 接口"
```

---

## Phase C — 后端 my-tasks 接口 + 我的任务磁贴

### Task C1: 后端 crud `get_my_tasks`（TDD）

**Files:**
- Create: `backend/app/crud/dashboard_mytasks.py`
- Test: `backend/tests/test_dashboard_mytasks.py`

- [ ] **Step 1: 写失败测试**

```python
import uuid
import datetime
import pytest
from app.crud.dashboard_mytasks import get_my_tasks
from app.models.models_project import Project, ProjectTask


@pytest.fixture
def me():
    return uuid.uuid4()


def _project(db):
    p = Project(id=uuid.uuid4(), code="PRJ-1", name="项目一", status="进行中", owner_id=uuid.uuid4())
    db.add(p); db.commit()
    return p


def _task(db, project_id, **kw):
    d = dict(id=uuid.uuid4(), project_id=project_id, code="T-1", name="任务一",
             task_type="任务", status="进行中", priority="中", sort_order=0)
    d.update(kw)
    t = ProjectTask(**d); db.add(t); db.commit()
    return t


def test_assigned_unfinished_included(db, me):
    p = _project(db)
    _task(db, p.id, assignee_id=me, status="进行中")
    tasks = get_my_tasks(db, me)
    assert len(tasks) == 1
    assert tasks[0]["project_name"] == "项目一"
    assert tasks[0]["name"] == "任务一"


def test_finished_excluded(db, me):
    p = _project(db)
    _task(db, p.id, assignee_id=me, status="已完成")
    assert get_my_tasks(db, me) == []


def test_others_task_excluded(db, me):
    p = _project(db)
    _task(db, p.id, assignee_id=uuid.uuid4(), status="进行中")
    assert get_my_tasks(db, me) == []


def test_planned_end_serialized(db, me):
    p = _project(db)
    _task(db, p.id, assignee_id=me, status="未开始", planned_end=datetime.date(2026, 6, 30))
    tasks = get_my_tasks(db, me)
    assert tasks[0]["planned_end"] == "2026-06-30"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && pytest tests/test_dashboard_mytasks.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
"""我的任务聚合：指派给我且未完成的项目任务。只读。"""
from sqlalchemy.orm import Session
from app.models.models_project import Project, ProjectTask

_DONE = {"已完成"}


def get_my_tasks(db: Session, user_id):
    rows = (
        db.query(ProjectTask, Project.name, Project.id)
        .join(Project, Project.id == ProjectTask.project_id)
        .filter(ProjectTask.assignee_id == user_id)
        .filter(~ProjectTask.status.in_(_DONE))
        .all()
    )
    out = []
    for task, project_name, project_id in rows:
        out.append({
            "project_id": str(project_id),
            "project_name": project_name,
            "task_id": str(task.id),
            "code": task.code,
            "name": task.name,
            "status": task.status,
            "priority": task.priority,
            "planned_end": task.planned_end.isoformat() if task.planned_end else None,
        })
    return out
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && pytest tests/test_dashboard_mytasks.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/crud/dashboard_mytasks.py backend/tests/test_dashboard_mytasks.py
git commit -m "feat(dashboard): get_my_tasks 聚合我的未完成任务（crud + 测试）"
```

### Task C2: 后端路由 `GET /projects/my-tasks`

**Files:**
- Modify: `backend/app/routers/projects.py`

- [ ] **Step 1: 顶部 import 追加**

```python
from app.crud.dashboard_mytasks import get_my_tasks
```

- [ ] **Step 2: 在 `@router.get("/{project_id}")` 路由之前新增（避免被 `{project_id}` 捕获）**

紧接 `@router.get("")`（列项目）之后、`@router.get("/{project_id}")` 之前插入：

```python
@router.get("/my-tasks")
async def my_tasks(db: Session = Depends(get_db),
                   current_user: User = Depends(require_permission("project:read"))):
    return {"items": get_my_tasks(db, current_user.id)}
```

- [ ] **Step 3: 冒烟**

Run: `cd backend && python -c "from app.routers.projects import router; paths=[r.path for r in router.routes]; print('my-tasks before param:', paths.index([p for p in paths if 'my-tasks' in p][0]) < paths.index([p for p in paths if '{project_id}' in p and p.endswith('{project_id}')][0]))"`
Expected: `my-tasks before param: True`

- [ ] **Step 4: 提交**

```bash
git add backend/app/routers/projects.py
git commit -m "feat(dashboard): 新增 GET /projects/my-tasks 路由"
```

### Task C3: 前端接入我的任务

**Files:**
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/pages/Dashboard/MyTasksTile.tsx`
- Modify: `frontend/src/pages/Dashboard/index.tsx`

- [ ] **Step 1: 类型（types/index.ts 追加）**

```typescript
export interface MyTaskItem {
  project_id: string;
  project_name: string;
  task_id: string;
  code: string;
  name: string;
  status: string;
  priority: string;
  planned_end: string | null;
}
```

- [ ] **Step 2: api（projectApi 内追加）**

在 `frontend/src/services/projectApi.ts` 的 `projectApi` 对象内追加：

```typescript
  myTasks: () => api.get('/projects/my-tasks'),
```

- [ ] **Step 3: MyTasksTile.tsx 完整实现**

```tsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Tile, EmptyState } from './tiles';
import { projectApi } from '../../services/projectApi';
import { overdueDays } from './lib/aggregate';
import type { MyTaskItem } from '../../types';

export function MyTasksTile({ onOverdue }: { onOverdue?: (n: number) => void }) {
  const [items, setItems] = useState<MyTaskItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let cancelled = false;
    projectApi.myTasks()
      .then((res) => {
        if (cancelled) return;
        const list: MyTaskItem[] = res.data?.items ?? [];
        setItems(list);
        const now = Date.now();
        onOverdue?.(list.filter((t) => overdueDays(t.planned_end, now) > 0).length);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoaded(true); });
    return () => { cancelled = true; };
  }, [onOverdue]);

  const now = Date.now();
  const overdueTotal = items.filter((t) => overdueDays(t.planned_end, now) > 0).length;
  return (
    <Tile title="我的任务" icon={<span>✅</span>} right={overdueTotal > 0 ? <span className="text-xs text-red-500">{overdueTotal} 逾期</span> : undefined}>
      {loaded && items.length === 0 ? <EmptyState text="暂无指派给你的任务" /> : (
        <div className="flex flex-col gap-2">
          {items.slice(0, 4).map((t) => {
            const od = overdueDays(t.planned_end, now);
            return (
              <Link key={t.task_id} to={`/projects/${t.project_id}`} className="flex items-center gap-2 text-sm hover:bg-gray-50 rounded px-1">
                <span className="w-3.5 h-3.5 border border-gray-300 rounded-sm shrink-0" />
                <span className="truncate flex-1 text-gray-700">{t.name}</span>
                <span className={`text-xs shrink-0 ${od > 0 ? 'text-red-500' : 'text-gray-400'}`}>
                  {od > 0 ? `逾期 ${od}天` : (t.planned_end || '')}
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </Tile>
  );
}
```

> 注：任务详情路由以实际项目路由为准（若无 `/projects/:id` 页则改为 `/projects`）。实现时在 `App.tsx` 确认项目详情路由路径。

- [ ] **Step 4: index.tsx 接入逾期计数**

```tsx
const [overdueCount, setOverdueCount] = useState(0);
// JSX：<MyTasksTile onOverdue={setOverdueCount} />
// GreetingHeader 的 overdueCount 用该 state
```

- [ ] **Step 5: 类型检查 + preview 验证**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无报错

preview：以有指派任务的用户登录，确认任务列出、逾期红字与"N 逾期"标记、问候语逾期数联动；无任务显示空态。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/services/projectApi.ts frontend/src/types/index.ts frontend/src/pages/Dashboard/MyTasksTile.tsx frontend/src/pages/Dashboard/index.tsx
git commit -m "feat(dashboard): 我的任务磁贴接入 my-tasks 接口"
```

### Task C4: 变更进行中 KPI 接入

**Files:**
- Modify: `frontend/src/pages/Dashboard/index.tsx`

- [ ] **Step 1: 用待办数派生"变更进行中"占位改为真实计数**

复用 Task B 的 `dashboardApi.getMyTodos` 已能给出待办；"变更进行中"应为全局 reviewing 数，取 `ecrApi.list({ status: 'reviewing', page_size: 1 })` 与 `ecoApi.list({ status: 'reviewing', page_size: 1 })` 的返回 `total` 求和。在 index.tsx 内新增：

```tsx
import { ecrApi, ecoApi } from '../../services/api';
// 组件内：
const [changeOpen, setChangeOpen] = useState(0);
useEffect(() => {
  let cancelled = false;
  Promise.allSettled([
    ecrApi.list({ status: 'reviewing', page_size: 1 }),
    ecoApi.list({ status: 'reviewing', page_size: 1 }),
  ]).then((rs) => {
    if (cancelled) return;
    const n = rs.reduce((sum, r) => sum + (r.status === 'fulfilled' ? (r.value.data?.total ?? 0) : 0), 0);
    setChangeOpen(n);
  });
  return () => { cancelled = true; };
}, []);
```

并删除原先 `const changeOpen = 0;`。

- [ ] **Step 2: 类型检查 + preview**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无报错。preview 确认"变更进行中" KPI 显示真实数字（若接口无 `total` 字段则回退为列表长度，实现时按实际响应结构适配）。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/Dashboard/index.tsx
git commit -m "feat(dashboard): 变更进行中 KPI 接入真实计数"
```

---

## Phase D — 二期（本计划不实现，另起计划）

- `最近访问` 升级为真浏览历史：在零件/部件/图文档/构型详情页打开时向 localStorage 写访问记录，`useRecentEdited` 增加从本地记录读取的分支。
- `my-todos` 扩展覆盖构型（`ProfileReviewer`）/物料（`InvReviewer`）审批。

---

## Self-Review

**Spec coverage：**
- 问候抬头 → Task A5(GreetingHeader) + A7 + B3/C3 联动计数 ✅
- 待我处理（ECR/ECO 一期）→ Phase B（B1 crud + B2 路由 + B3 前端）✅
- 我的任务 → Phase C（C1 crud + C2 路由 + C3 前端）✅
- 最近访问（一期"最近编辑"）→ A3(dedupeRecentRefs) + A4(useRecentEdited) + A5(RecentItemsTile) ✅
- 我的收藏 → A3(flattenFavorites) + A4(useFavorites) + A5(FavoritesTile) ✅
- 全局 KPI（含变更进行中）→ A5(KpiStrip) + A7 + C4 ✅
- 状态分布分段条 → A2(statusDistribution) + A5(StatusDistributionTile) ✅
- 系统动态流 → A3(formatActivity) + A4(useActivityFeed) + A5(ActivityFeedTile) ✅
- 两区响应式布局 + 空态 → A5(Tile/EmptyState) + A7 ✅
- 不新增表/字段 → 两接口均只读现有表 ✅
- 二期（浏览埋点 / 构型物料）→ Phase D 明确另起 ✅

**Placeholder scan：** 无 TBD/TODO；两处"注"为实现时的合理适配点（外键列写法、任务详情路由、接口 total 字段），均给出明确回退方案，非占位。

**Type consistency：** `MyTodoItem`/`MyTaskItem` 前后端字段一致（type/kind/number/title/priority/status/updated_at；project_id/project_name/task_id/code/name/status/priority/planned_end）；`get_my_todos` 返回键与前端 `MyTodoItem` 对齐；`get_my_tasks` 返回键与 `MyTaskItem` 对齐；`Tile`/`EmptyState`/`relativeTime`/`overdueDays`/`statusDistribution` 在定义任务(A1/A2/A5)先于使用任务(A6/B3/C3)。
