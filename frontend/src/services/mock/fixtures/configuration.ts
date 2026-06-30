import type { MockRoute } from '../types';

// 构型管理示例数据（沿用 myPDM Configuration 页界面，仅补 mock 数据）。
const items = [
  { id: 'ci-1', code: 'CFG-001', name: '标准型配置', spec: 'A 型', version: 'A', status: 'released', remark: '量产基线配置' },
  { id: 'ci-2', code: 'CFG-002', name: '增强型配置', spec: 'B 型', version: 'A', status: 'draft', remark: '研发中，含选装泵组件' },
  { id: 'ci-3', code: 'CFG-003', name: '出口型配置', spec: 'C 型', version: 'B', status: 'frozen', remark: '送审冻结版' },
];

export const configurationRoutes: MockRoute[] = [
  {
    method: 'get',
    pattern: /^\/configurations\/items$/,
    handler: ({ query }) => {
      const s = (query.get('search') || '').trim();
      const filtered = items.filter((it) => !s || it.code.includes(s) || it.name.includes(s));
      return { items: filtered, total: filtered.length };
    },
  },
];
