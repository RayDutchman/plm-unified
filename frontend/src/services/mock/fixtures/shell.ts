import type { MockRoute } from '../types';

// 全局数据预载（stores/data.ts）+ 同步轮询（syncService）所需的列表接口。
// Phase 0 先返回空/极简，让外壳与各页能渲染；Phase 2+ 再按域充实真实假数据。
// stores/data.ts 的 extractData 同时兼容数组与 {items}，故两种 shape 均可。

const sampleUsers = [
  { id: 'u-admin', username: 'admin', real_name: '系统管理员', role: 'admin', department: '研发', phone: '', status: 'active', created_at: '2026-06-29T00:00:00Z', updated_at: '2026-06-29T00:00:00Z' },
  { id: 'u-eng', username: 'engineer', real_name: '张工', role: 'engineer', department: '设计', phone: '', status: 'active', created_at: '2026-06-29T00:00:00Z', updated_at: '2026-06-29T00:00:00Z' },
  { id: 'u-prod', username: 'prod', real_name: '李工', role: 'production', department: '生产', phone: '', status: 'active', created_at: '2026-06-29T00:00:00Z', updated_at: '2026-06-29T00:00:00Z' },
];

const emptyPage = { items: [], total: 0 };

export const shellRoutes: MockRoute[] = [
  { method: 'get', pattern: /^\/parts\/$/, handler: () => emptyPage },
  { method: 'get', pattern: /^\/assemblies\/$/, handler: () => emptyPage },
  { method: 'get', pattern: /^\/users\/$/, handler: () => ({ items: sampleUsers, total: sampleUsers.length }) },
];
