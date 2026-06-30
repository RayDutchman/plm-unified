# 前端 Mock 适配层 + 独立运行（Phase 0 + Phase 1）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development 或 superpowers:executing-plans 逐任务执行。Steps 用 `- [ ]` 跟踪。

**Goal:** 让已复制的 myPDM 前端在 plm-unified 中**脱离后端独立运行**：在单一 axios 实例上注入 mock 适配层（`VITE_USE_MOCK` 开关），先打通"登录 → 主界面外壳 → 用户看板（Dashboard + Board）"垂直切片。

**Architecture:** 所有请求走 `services/api.ts` 的单一 axios 实例 `api`（baseURL `/api`）。Mock 模式下用 `api.defaults.adapter = mockAdapter` 短路 HTTP，按 `method + url` 路由到 fixtures；未命中接口 → `console.warn` + 501（暴露缺口）。页面/`xxxApi`/拦截器零改动。

**Tech Stack:** Vite 5、React 18、TypeScript、axios 1.7、zustand、react-router 6、vitest + jsdom。Node 24 / npm 11。

---

## 对应设计

实现已确认的设计（前端内 mock 适配层 + 增量 Phase）。本计划只覆盖 **Phase 0（地基）+ Phase 1（用户看板）**；Phase 2–6（零部件/构型/变更/库存/系统设置）后续另起计划。

## 已知事实（探查结论）

- 入口 `src/main.tsx` 极简，是注入 mock 的位置。
- `src/services/api.ts`：单 axios 实例 `api`（baseURL `/api`），请求拦截器加 Bearer，响应拦截器仅对 **401** 自动 refresh（`doRefresh` 用裸 `axios.post('/api/auth/refresh')`，不走 `api` 实例 —— mock 模式下不会 401，故不受影响）。
- 登录流程（`pages/Login.tsx`）：`authApi.login()` 读 `{access_token, refresh_token}` → `setUser(null, token)` → `authApi.getCurrentUser()` 读 `User` → `setUser(user, token)` → `navigate('/')`。
- `User` 类型：`{id, username, real_name, role('admin'|'engineer'|'production'|'guest'), department?, phone?, status, created_at, updated_at}`。
- `stores/auth.ts`：zustand persist（`auth-storage`），`setUser(user, token)`，`hasRole`。角色门 + `permissions.generated.ts` 决定菜单可见性。
- build 前置：`prebuild`/`gen:perms` 跑 `python ../tools/gen_permissions.py` 生成 `src/constants/permissions.generated.ts`（该文件已存在并入库）。
- 侧栏导航 12 项（`components/Layout.tsx`）：仪表盘/用户看板/管理工具(bom)/构型管理/零部件管理/图文档管理/变更管理/库存管理/项目管理/用户管理/系统设置。

## File Structure

| 文件 | 职责 |
|---|---|
| `frontend/.env.development` | `VITE_USE_MOCK=1`（创建） |
| `frontend/src/services/mock/types.ts` | `MockRoute`/`MockHandler` 类型 |
| `frontend/src/services/mock/adapter.ts` | axios mock 适配器：路由匹配 + 501 兜底 + 延迟 |
| `frontend/src/services/mock/routes.ts` | 汇总各域路由数组 |
| `frontend/src/services/mock/fixtures/auth.ts` | 登录/me/改密 假数据 + 路由 |
| `frontend/src/services/mock/fixtures/dashboard.ts` | 仪表盘 stats + 用户列表 等 |
| `frontend/src/services/mock/fixtures/board.ts` | 用户看板（文件夹树/关联项/共享） |
| `frontend/src/services/mock/index.ts` | `installMock()`：装配 adapter 到 `api` |
| `frontend/src/services/mock/adapter.test.ts` | adapter 单元测试（vitest） |
| `frontend/src/main.tsx` | 条件 `installMock()`（修改） |

命令在 `frontend/` 下，用 `npm`。

---

### Task 0.1: 装依赖 + build 基线

**Files:** 无（环境）

- [ ] **Step 1: 安装依赖**
Run（`frontend/`）: `npm install`
Expected: 成功，生成 `node_modules`。

- [ ] **Step 2: 生成权限常量（prebuild 依赖的 python 工具）**
Run: `npm run gen:perms`
Expected: 重新生成 `src/constants/permissions.generated.ts`，无报错。（需本机有 python；若失败，确认 `python ../tools/gen_permissions.py` 可独立跑。）

- [ ] **Step 3: 类型/构建基线**
Run: `npx tsc --noEmit`
Expected: 通过，或记录现存类型错误清单（若已有历史错误，作为基线记下，不在本计划修复无关错误）。

- [ ] **Step 4: 提交（仅在有需要入库的改动时）**
本任务通常无源码改动；若 `gen:perms` 产生 diff 则：
```bash
git add frontend/src/constants/permissions.generated.ts
git commit -m "chore(frontend): 重新生成权限常量"
```

---

### Task 0.2: Mock 适配器内核（TDD）

**Files:**
- Create: `frontend/src/services/mock/types.ts`
- Create: `frontend/src/services/mock/adapter.ts`
- Create: `frontend/src/services/mock/routes.ts`（先空数组）
- Create: `frontend/src/services/mock/adapter.test.ts`

- [ ] **Step 1: 写失败测试** — `adapter.test.ts`：
```ts
import { describe, it, expect, vi } from 'vitest';
import { mockAdapter } from './adapter';
import type { InternalAxiosRequestConfig } from 'axios';

function cfg(method: string, url: string, data?: any): InternalAxiosRequestConfig {
  return { method, url, data, headers: {} as any } as InternalAxiosRequestConfig;
}

describe('mockAdapter', () => {
  it('命中路由返回 fixture（status 200）', async () => {
    const resp = await mockAdapter(cfg('post', '/auth/token'));
    expect(resp.status).toBe(200);
    expect(resp.data.access_token).toBeTruthy();
  });

  it('解析 path 参数', async () => {
    // /auth/me 无参数；用一个带参路由验证：GET /dashboard/folders/:id/shares
    const resp = await mockAdapter(cfg('get', '/dashboard/folders/abc/shares'));
    expect(resp.status).toBe(200);
    expect(Array.isArray(resp.data)).toBe(true);
  });

  it('未命中接口 → 501 reject 且 warn', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    await expect(mockAdapter(cfg('get', '/nope/123'))).rejects.toMatchObject({ code: '501' });
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**
Run: `npx vitest run src/services/mock/adapter.test.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写 types.ts**
```ts
import type { InternalAxiosRequestConfig } from 'axios';

export interface MockCtx {
  config: InternalAxiosRequestConfig;
  params: Record<string, string>;
  body: any;
  query: URLSearchParams;
}

export type MockHandler = (ctx: MockCtx) => any | Promise<any>;

export interface MockRoute {
  method: 'get' | 'post' | 'put' | 'delete' | 'patch';
  pattern: RegExp;        // 匹配 config.url（去掉 baseURL 与 query）
  keys?: string[];        // 捕获组名 → params
  handler: MockHandler;
}
```

- [ ] **Step 4: 写 adapter.ts**
```ts
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { AxiosError } from 'axios';
import { routes } from './routes';

const DELAY = 100; // 模拟网络延迟

function parseBody(data: unknown): any {
  if (data == null) return undefined;
  if (typeof data === 'string') {
    try { return JSON.parse(data); } catch { return data; }
  }
  return data;
}

export const mockAdapter: AxiosAdapter = async (
  config: InternalAxiosRequestConfig,
): Promise<AxiosResponse> => {
  const method = (config.method || 'get').toLowerCase();
  const fullUrl = config.url || '';
  const [path, qs] = fullUrl.split('?');

  for (const r of routes) {
    if (r.method !== method) continue;
    const m = r.pattern.exec(path);
    if (!m) continue;
    const params: Record<string, string> = {};
    (r.keys || []).forEach((k, i) => { params[k] = m[i + 1]; });
    const data = await r.handler({
      config, params, body: parseBody(config.data),
      query: new URLSearchParams(qs || ''),
    });
    await new Promise((res) => setTimeout(res, DELAY));
    return { data, status: 200, statusText: 'OK', headers: {}, config, request: {} };
  }

  console.warn(`[mock] 未实现的接口: ${method.toUpperCase()} ${path}`);
  await new Promise((res) => setTimeout(res, DELAY));
  return Promise.reject(
    new AxiosError(`mock 未实现: ${method} ${path}`, '501', config, null, {
      data: { detail: 'mock not implemented' }, status: 501,
      statusText: 'Not Implemented', headers: {}, config, request: {},
    } as AxiosResponse),
  );
};
```

- [ ] **Step 5: 写 routes.ts（先引入 auth + board，使带参测试通过）**
```ts
import type { MockRoute } from './types';
import { authRoutes } from './fixtures/auth';
import { boardRoutes } from './fixtures/board';
import { dashboardRoutes } from './fixtures/dashboard';

export const routes: MockRoute[] = [
  ...authRoutes,
  ...dashboardRoutes,
  ...boardRoutes,
];
```
> 本步依赖 Task 0.3 的 `auth.ts` 与 Task 1.1/1.2 的 fixtures。**执行顺序**：先建 `fixtures/auth.ts`（下方 Task 0.3 Step 1 的代码），`fixtures/dashboard.ts`、`fixtures/board.ts` 可先建为 `export const xxxRoutes = []` 占位，Task 1 再填。带参测试用例（`/dashboard/folders/:id/shares`）属 board，确保 `boardRoutes` 至少含该路由。

- [ ] **Step 6: 跑测试确认通过**
Run: `npx vitest run src/services/mock/adapter.test.ts`
Expected: PASS（3 passed）

- [ ] **Step 7: 提交**
```bash
git add frontend/src/services/mock/
git commit -m "feat(frontend): 添加 axios mock 适配器内核与路由表"
```

---

### Task 0.3: Mock 登录打通 + 注入开关

**Files:**
- Create: `frontend/.env.development`
- Create: `frontend/src/services/mock/fixtures/auth.ts`
- Create: `frontend/src/services/mock/index.ts`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: 写 fixtures/auth.ts**
```ts
import type { MockRoute } from '../types';

export const mockAdminUser = {
  id: '00000000-0000-0000-0000-000000000010',
  username: 'admin',
  real_name: '系统管理员',
  role: 'admin',
  department: '研发',
  phone: '',
  status: 'active',
  created_at: '2026-06-29T00:00:00Z',
  updated_at: '2026-06-29T00:00:00Z',
};

export const authRoutes: MockRoute[] = [
  { method: 'post', pattern: /^\/auth\/token$/,
    handler: () => ({ access_token: 'mock-access-token', refresh_token: 'mock-refresh-token', token_type: 'bearer' }) },
  { method: 'get', pattern: /^\/auth\/me$/, handler: () => mockAdminUser },
  { method: 'post', pattern: /^\/auth\/change-password$/, handler: () => ({ message: '密码修改成功' }) },
];
```

- [ ] **Step 2: 写 index.ts（installMock）**
```ts
import api from '../api';            // 见下方注意：api 实例需可导入
import { mockAdapter } from './adapter';

/** 在 mock 模式下，把 axios 默认 adapter 换成本地 mock。 */
export function installMock(): void {
  // @ts-expect-error 运行时挂载
  api.defaults.adapter = mockAdapter;
  console.info('[mock] 已启用前端 mock 适配层（VITE_USE_MOCK=1）');
}
```
> **注意**：`services/api.ts` 当前 `const api = axios.create(...)` 未 `export` 该实例。需在 `api.ts` 末尾补 `export default api;`（不影响现有具名导出）。本步顺带加这一行。

- [ ] **Step 3: 在 api.ts 导出实例**
在 `frontend/src/services/api.ts` 末尾添加：
```ts
export default api;
```

- [ ] **Step 4: 写 .env.development**
```
VITE_USE_MOCK=1
```

- [ ] **Step 5: 改 main.tsx 注入**
```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

if (import.meta.env.VITE_USE_MOCK === '1') {
  const { installMock } = await import('./services/mock');
  installMock();
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```
> 顶层 `await import` 需要模块为 ESM（Vite 默认支持）。若 lint 报顶层 await，改为：在 `installMock` 同步 import（`import { installMock } from './services/mock'`）并直接 `if (...) installMock();`。

- [ ] **Step 6: 启动并验证登录 → 进入主界面**
Run: `npm run dev`（后台启动），浏览器开 `http://localhost:5173`
手动验证：
- 登录页输入任意用户名/密码 → 成功跳转 `/`（dashboard）
- 控制台出现 `[mock] 已启用…`；不应有 `/auth/*` 的 501 warn
- 顶部/侧栏渲染，用户显示"系统管理员"
> 自动化冒烟（可选）：用 vitest + jsdom 渲染 `Login` 并断言提交后 `useAuthStore` 的 `isAuthenticated` 为 true（若页面依赖过多可跳过，以手动 dev 验证为准）。

- [ ] **Step 7: 提交**
```bash
git add frontend/.env.development frontend/src/services/mock/ frontend/src/services/api.ts frontend/src/main.tsx
git commit -m "feat(frontend): mock 登录打通 + VITE_USE_MOCK 注入开关"
```

---

### Task 0.4: 主界面外壳 + 侧栏渲染验证

**Files:** 视情况补 fixtures（首屏可能触发的少量接口）

- [ ] **Step 1: 跑 dev，记录首屏 501 warn**
登录后停在 `/dashboard`，打开控制台，记录所有 `[mock] 未实现的接口: ...` 行。这些是 Dashboard 首屏触发的接口（如 `/dashboard/stats`、`/users` 等）。

- [ ] **Step 2: 为外壳级接口补最小 fixture**
对"主界面外壳/导航必需"的接口（非 Dashboard 业务数据）补最小返回，确保布局不报错。常见：当前用户、未读计数等。把这些加入 `fixtures/auth.ts` 或新建 `fixtures/shell.ts` 并在 `routes.ts` 注册。
> Dashboard 的业务数据留给 Task 1.1；本步只解决"外壳渲染"所必需的接口。

- [ ] **Step 3: 验证侧栏 12 项可见**
admin 角色下，侧栏应显示全部菜单项（仪表盘/用户看板/管理工具/构型管理/零部件管理/图文档管理/变更管理/库存管理/项目管理/用户管理/系统设置）。逐项点击应能切换路由（业务页可能仍报 501，正常 —— 后续 Phase 覆盖）。

- [ ] **Step 4: 提交**
```bash
git add frontend/src/services/mock/
git commit -m "feat(frontend): 主界面外壳所需接口 mock，侧栏渲染通过"
```

---

### Task 1.1: 用户看板 — 仪表盘（Dashboard）

**Files:**
- Create/补充: `frontend/src/services/mock/fixtures/dashboard.ts`

- [ ] **Step 1: 枚举 Dashboard 调用的接口**
`npm run dev` 停在 `/dashboard`，记录全部 501 warn。对照 `pages/Dashboard.tsx` 确认它调用的 API（已知含 `dashboardApi.getStats` → `/dashboard/stats`，以及用户列表等）。

- [ ] **Step 2: 写 fixtures/dashboard.ts**
按 Step 1 枚举的接口提供自洽假数据。骨架：
```ts
import type { MockRoute } from '../types';

const stats = {
  parts: 128, assemblies: 32, documents: 240,
  ecr_open: 5, eco_open: 3, inventory_low: 7,
  // 字段名需与 Dashboard.tsx 读取的一致（按 Step 1 实际报错/读取调整）
};

export const dashboardRoutes: MockRoute[] = [
  { method: 'get', pattern: /^\/dashboard\/stats$/, handler: () => stats },
  // 视 Step 1 结果补充：/users 等
];
```
> 字段名以 `Dashboard.tsx` 实际解构为准 —— 若组件读 `data.partCount` 而非 `data.parts`，按组件改 fixture（保持组件不动）。

- [ ] **Step 3: 验证 /dashboard 渲染**
`npm run dev` → `/dashboard` 无 501 warn、统计卡片/图表渲染出假数据、无 React 崩溃。

- [ ] **Step 4: 提交**
```bash
git add frontend/src/services/mock/fixtures/dashboard.ts frontend/src/services/mock/routes.ts
git commit -m "feat(frontend): 仪表盘页 mock 数据，独立渲染通过"
```

---

### Task 1.2: 用户看板 — 看板（Board）

**Files:**
- Create/补充: `frontend/src/services/mock/fixtures/board.ts`

- [ ] **Step 1: 枚举 Board 调用的接口**
`/board` 页记录 501 warn。已知 `boardApi.getDashboard` → `GET /dashboard/`（返回文件夹树 + 关联项 + 共享文件夹），及文件夹/共享相关增删改。

- [ ] **Step 2: 写 fixtures/board.ts**
```ts
import type { MockRoute } from '../types';

const dashboardTree = {
  folders: [
    { id: 'f1', name: '我的收藏', parent_id: null, items: [], children: [] },
    { id: 'f2', name: '常用零件', parent_id: null, items: [], children: [] },
  ],
  shared_folders: [],
};

export const boardRoutes: MockRoute[] = [
  { method: 'get', pattern: /^\/dashboard\/$/, handler: () => dashboardTree },
  { method: 'post', pattern: /^\/dashboard\/init$/, handler: () => dashboardTree },
  { method: 'post', pattern: /^\/dashboard\/folders$/, body: undefined as any,
    handler: ({ body }) => ({ id: 'f-new', name: body?.name ?? '新文件夹', parent_id: body?.parent_id ?? null, items: [], children: [] }) },
  { method: 'put', pattern: /^\/dashboard\/folders\/([^/]+)$/, keys: ['id'],
    handler: ({ params, body }) => ({ id: params.id, name: body?.name ?? '文件夹', parent_id: body?.parent_id ?? null, items: [], children: [] }) },
  { method: 'delete', pattern: /^\/dashboard\/folders\/([^/]+)$/, keys: ['id'], handler: () => ({}) },
  { method: 'post', pattern: /^\/dashboard\/items$/, handler: () => ({}) },
  { method: 'delete', pattern: /^\/dashboard\/items\/([^/]+)$/, keys: ['id'], handler: () => ({}) },
  { method: 'get', pattern: /^\/dashboard\/folders\/([^/]+)\/shares$/, keys: ['id'], handler: () => [] },
];
```
> 删去 `body: undefined as any` 这类占位（仅示意）；以 `boardApi` 实际方法签名为准对齐路由。返回结构以 `Board.tsx`/`pages/Board` 解构为准调整（保持组件不动）。

- [ ] **Step 3: 验证 /board 渲染**
`/board` 文件夹树渲染假数据，新建/重命名/删除文件夹等交互不崩（mock 返回让 UI 乐观更新或刷新）。无未实现 501。

- [ ] **Step 4: 提交**
```bash
git add frontend/src/services/mock/fixtures/board.ts frontend/src/services/mock/routes.ts
git commit -m "feat(frontend): 用户看板页 mock 数据，独立渲染通过"
```

---

## Self-Review（已执行）

- **设计覆盖**：单点注入（adapter 替换 `api.defaults.adapter`）+ 开关（`.env`）+ 501 暴露缺口 + 增量 fixtures，全部落到 Task 0.2/0.3 与 1.1/1.2。
- **零改页面**：仅改 `main.tsx`（注入）与 `api.ts`（补 `export default api`），不动任何页面/`xxxApi`/拦截器。
- **占位符**：fixtures 的具体字段名标注"以组件实际解构为准"，因为只有 `npm run dev` 跑起来看 warn/报错才能精确确定 —— 这是前端 mock 的固有迭代环节，已在每个 Task 的 Step 1 明确"先枚举再填"。
- **次序耦合**：`routes.ts`（0.2 Step 5）引用 dashboard/board fixtures —— 已说明先建空数组占位、Task 1 再填。

## 后续（不在本计划内）

- Phase 2–6：零部件管理（+BOM）、构型管理、变更管理、库存管理、系统设置 —— 每个一组 fixtures + 路由，复用本 adapter，另起计划。
- 切真后端：删 `.env.development` 的 `VITE_USE_MOCK` 或置 0，请求自动回到真实 `/api`（M2/M3 后端就绪后）。
