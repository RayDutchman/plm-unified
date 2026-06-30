import type { MockRoute } from '../types';

const now = new Date().toISOString();

const customFieldDefs = [
  {
    id: 'cfd-1', name: '材质', field_key: 'material', field_type: 'select',
    options: ['碳钢', '不锈钢304', '不锈钢316', '铝合金', '铜合金'],
    is_required: true, applies_to: ['part'], sort_order: 1,
    created_at: '2026-06-01T00:00:00Z', updated_at: '2026-06-01T00:00:00Z',
  },
  {
    id: 'cfd-2', name: '表面处理', field_key: 'surface_treatment', field_type: 'multiselect',
    options: ['镀锌', '镀铬', '发黑', '喷漆', '阳极氧化'],
    is_required: false, applies_to: ['part', 'assembly'], sort_order: 2,
    created_at: '2026-06-02T00:00:00Z', updated_at: '2026-06-02T00:00:00Z',
  },
  {
    id: 'cfd-3', name: '备注', field_key: 'notes', field_type: 'text',
    is_required: false, applies_to: ['part', 'assembly', 'document'], sort_order: 3,
    created_at: '2026-06-03T00:00:00Z', updated_at: '2026-06-03T00:00:00Z',
  },
];

const logs = [
  { id: 'log-1', user_id: 'u-admin', username: '系统管理员', action: 'login', target_type: 'user', target_id: 'u-admin', detail: '用户登录系统', ip: '192.168.1.100', created: '2026-06-30T08:00:00Z' },
  { id: 'log-2', user_id: 'u-eng', username: '张工', action: 'create', target_type: 'part', target_id: 'pm-001', detail: '创建零件：螺栓 M8×30', ip: '192.168.1.101', created: '2026-06-29T14:30:00Z' },
  { id: 'log-3', user_id: 'u-eng', username: '张工', action: 'update', target_type: 'part', target_id: 'pm-001', detail: '更新零件版本：A→B', ip: '192.168.1.101', created: '2026-06-29T15:00:00Z' },
  { id: 'log-4', user_id: 'u-admin', username: '系统管理员', action: 'create', target_type: 'user', target_id: 'u-prod', detail: '创建用户：李工', ip: '192.168.1.100', created: '2026-06-29T10:00:00Z' },
  { id: 'log-5', user_id: 'u-prod', username: '李工', action: 'update', target_type: 'custom_field', target_id: 'cfd-1', detail: '修改自定义字段：材质选项', ip: '192.168.1.102', created: '2026-06-28T16:00:00Z' },
  { id: 'log-6', user_id: 'u-eng', username: '张工', action: 'delete', target_type: 'document', target_id: 'doc-old', detail: '删除废旧图文档', ip: '192.168.1.101', created: '2026-06-27T11:00:00Z' },
  { id: 'log-7', user_id: 'u-admin', username: '系统管理员', action: 'login', target_type: 'user', target_id: 'u-admin', detail: '用户登录系统', ip: '192.168.1.100', created: '2026-06-30T07:30:00Z' },
];

export const settingsRoutes: MockRoute[] = [
  // 自定义字段定义
  {
    method: 'get',
    pattern: /^\/custom-fields\/definitions\/$/,
    handler: () => customFieldDefs,
  },
  {
    method: 'post',
    pattern: /^\/custom-fields\/definitions\/$/,
    handler: ({ body }) => ({
      id: `cfd-${Date.now()}`, ...body, sort_order: customFieldDefs.length + 1,
      created_at: now, updated_at: now,
    }),
  },
  {
    method: 'put',
    pattern: /^\/custom-fields\/definitions\/([^/]+)$/,
    handler: ({ params, body }) => ({ ...customFieldDefs.find((d) => d.id === params[0]), ...body, updated_at: now }),
  },
  { method: 'delete', pattern: /^\/custom-fields\/definitions\/([^/]+)$/, handler: () => ({ message: '已删除' }) },
  { method: 'put', pattern: /^\/custom-fields\/definitions\/reorder$/, handler: () => ({ message: '已排序' }) },

  // 自定义字段值
  {
    method: 'get',
    pattern: /^\/custom-fields\/values\/([^/]+)\/([^/]+)$/,
    handler: () => [
      { field_id: 'cfd-1', field_key: 'material', field_name: '材质', field_type: 'select', value: '不锈钢304' },
      { field_id: 'cfd-2', field_key: 'surface_treatment', field_name: '表面处理', field_type: 'multiselect', value: ['镀锌'] },
    ],
  },
  {
    method: 'get',
    pattern: /^\/custom-fields\/values\/batch$/,
    handler: () => ({}),
  },
  {
    method: 'put',
    pattern: /^\/custom-fields\/values\/([^/]+)\/([^/]+)$/,
    handler: () => ({ message: '已保存' }),
  },
  { method: 'post', pattern: /^\/custom-fields\/reset-data$/, handler: () => ({ message: '已重置' }) },

  // 操作日志
  {
    method: 'get',
    pattern: /^\/logs\/$/,
    handler: ({ query }) => {
      const userId = query.get('user_id') || '';
      const targetType = query.get('target_type') || '';
      const action = query.get('action') || '';
      const startDate = query.get('start_date') || '';
      const endDate = query.get('end_date') || '';
      let items = logs;
      if (userId) items = items.filter((l) => l.user_id === userId);
      if (targetType) items = items.filter((l) => l.target_type === targetType);
      if (action) items = items.filter((l) => l.action === action);
      if (startDate) items = items.filter((l) => l.created >= startDate);
      if (endDate) items = items.filter((l) => l.created <= endDate);
      return { items, total: items.length };
    },
  },

  // 用户组
  {
    method: 'get',
    pattern: /^\/user-groups\/$/,
    handler: () => ({
      items: [
        { id: 'ug-1', name: '管理员组', description: '系统管理员组', member_count: 1, created_at: now },
        { id: 'ug-2', name: '设计组', description: '研发设计人员', member_count: 2, created_at: now },
      ],
      total: 2,
    }),
  },
  { method: 'post', pattern: /^\/user-groups\/$/, handler: ({ body }) => ({ id: `ug-${Date.now()}`, ...body, created_at: now }) },
  { method: 'put', pattern: /^\/user-groups\/([^/]+)$/, handler: ({ params, body }) => ({ id: params[0], ...body, updated_at: now }) },
  { method: 'delete', pattern: /^\/user-groups\/([^/]+)$/, handler: () => ({ message: '已删除' }) },
  {
    method: 'get',
    pattern: /^\/user-groups\/([^/]+)\/members$/,
    handler: ({ params }) => {
      if (params[0] === 'ug-1') return { items: [{ user_id: 'u-admin', user_name: '系统管理员', role: 'admin' }] };
      return { items: [{ user_id: 'u-eng', user_name: '张工', role: 'engineer' }, { user_id: 'u-prod', user_name: '李工', role: 'production' }] };
    },
  },
  { method: 'put', pattern: /^\/user-groups\/([^/]+)\/members$/, handler: () => ({ message: '已更新成员' }) },
];
