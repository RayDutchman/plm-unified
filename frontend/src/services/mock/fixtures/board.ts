import type { MockRoute } from '../types';

// 用户看板：文件夹树 + 关联项 + 共享（结构以 Board 页实际解构为准，Task 1.2 校正）
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
  {
    method: 'post',
    pattern: /^\/dashboard\/folders$/,
    handler: ({ body }) => ({
      id: 'f-new', name: body?.name ?? '新文件夹', parent_id: body?.parent_id ?? null, items: [], children: [],
    }),
  },
  {
    method: 'put',
    pattern: /^\/dashboard\/folders\/([^/]+)$/,
    keys: ['id'],
    handler: ({ params, body }) => ({
      id: params.id, name: body?.name ?? '文件夹', parent_id: body?.parent_id ?? null, items: [], children: [],
    }),
  },
  { method: 'delete', pattern: /^\/dashboard\/folders\/([^/]+)$/, keys: ['id'], handler: () => ({}) },
  { method: 'post', pattern: /^\/dashboard\/items$/, handler: () => ({}) },
  { method: 'delete', pattern: /^\/dashboard\/items\/([^/]+)$/, keys: ['id'], handler: () => ({}) },
  { method: 'get', pattern: /^\/dashboard\/folders\/([^/]+)\/shares$/, keys: ['id'], handler: () => [] },
];
