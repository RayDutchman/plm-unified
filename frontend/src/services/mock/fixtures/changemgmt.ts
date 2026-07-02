import type { MockRoute } from '../types';

const now = new Date().toISOString();

const reviewers = [
  { user_id: 'u-admin', user_name: '系统管理员', role: 'reviewer', seq: 1 },
  { user_id: 'u-eng', user_name: '张工', role: 'reviewer', seq: 2 },
];

const ecrList = [
  {
    id: 'ecr-1',
    ecr_number: 'ECR-2026-001',
    title: '螺栓材质从碳钢改为不锈钢304',
    description: '因客户需求变更，所有M8螺栓材质从碳钢改为不锈钢304，提升耐腐蚀性能。',
    reason: '客户需求变更 - 海洋环境使用要求',
    priority: 'high',
    category: '材料变更',
    status: 'reviewing',
    review_mode: 'all',
    creator_id: 'u-eng',
    creator_name: '张工',
    reviewers,
    reviewers_count: 2,
    approved_count: 1,
    affected_count: 3,
    document_links: [],
    created_at: '2026-06-25T08:00:00Z',
    updated_at: '2026-06-29T10:00:00Z',
  },
  {
    id: 'ecr-2',
    ecr_number: 'ECR-2026-002',
    title: '泵组件增加密封圈及O型圈',
    description: '为提升泵组件密封性能，在法兰连接处增加密封圈，轴封处增加O型圈。',
    reason: '设计优化 - 降低泄漏风险',
    priority: 'urgent',
    category: '结构变更',
    status: 'draft',
    review_mode: 'any',
    creator_id: 'u-prod',
    creator_name: '李工',
    reviewers: [reviewers[0]],
    reviewers_count: 1,
    approved_count: 0,
    affected_count: 5,
    document_links: [],
    created_at: '2026-06-28T14:00:00Z',
    updated_at: '2026-06-28T14:00:00Z',
  },
  {
    id: 'ecr-3',
    ecr_number: 'ECR-2026-003',
    title: '支架壁厚从2mm增至3mm',
    description: '强度分析表明支架在极端工况下安全系数不足，壁厚需增加。',
    reason: 'CAE 分析反馈 - 安全系数不足',
    priority: 'normal',
    category: '尺寸变更',
    status: 'approved',
    review_mode: 'all',
    creator_id: 'u-eng',
    creator_name: '张工',
    reviewers,
    reviewers_count: 2,
    approved_count: 2,
    affected_count: 1,
    document_links: [],
    reviewed_at: '2026-06-27T16:00:00Z',
    created_at: '2026-06-20T09:00:00Z',
    updated_at: '2026-06-27T16:00:00Z',
    eco_id: 'eco-1',
  },
  {
    id: 'ecr-4',
    ecr_number: 'ECR-2026-004',
    title: '出口型配置取消部分选装件',
    description: '根据出口国法规要求，取消不符合当地认证的选装泵组件。',
    reason: '法规合规要求',
    priority: 'low',
    category: '配置变更',
    status: 'closed',
    review_mode: 'all',
    creator_id: 'u-admin',
    creator_name: '系统管理员',
    reviewers,
    reviewers_count: 2,
    approved_count: 2,
    affected_count: 0,
    document_links: [],
    created_at: '2026-06-15T10:00:00Z',
    updated_at: '2026-06-22T09:00:00Z',
    closed_at: '2026-06-22T09:00:00Z',
  },
];

const ecoList = [
  {
    id: 'eco-1',
    eco_number: 'ECO-2026-001',
    title: '执行：支架壁厚增至3mm',
    description: '变更支架图纸和工艺文件，将壁厚从2mm改为3mm。',
    reason: '关联 ECR-2026-003 批准执行',
    priority: 'normal',
    category: '尺寸变更',
    status: 'executing',
    review_mode: 'all',
    creator_id: 'u-eng',
    creator_name: '张工',
    reviewers,
    reviewers_count: 2,
    approved_count: 2,
    execution_count: 3,
    execution_completed_count: 1,
    document_links: [],
    ecr_id: 'ecr-3',
    ecr_number: 'ECR-2026-003',
    created_at: '2026-06-28T08:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
    execution_items: [
      {
        id: 'ei-1',
        eco_id: 'eco-1',
        source: 'ecr',
        entity_type: 'part',
        entity_id: 'pm-002',
        entity_code: 'P-002',
        entity_name: '支架',
        entity_version: 'A',
        action: 'upgrade',
        status: 'completed',
        sort_order: 1,
        new_version: 'B',
        executed_at: '2026-06-29T10:00:00Z',
      },
      {
        id: 'ei-2',
        eco_id: 'eco-1',
        source: 'ecr',
        entity_type: 'assembly',
        entity_id: 'pm-100',
        entity_code: 'ASM-100',
        entity_name: '泵组件',
        entity_version: 'A',
        action: 'upgrade',
        status: 'in_progress',
        sort_order: 2,
      },
      {
        id: 'ei-3',
        eco_id: 'eco-1',
        source: 'ecr',
        entity_type: 'assembly',
        entity_id: 'pm-200',
        entity_code: 'ASM-200',
        entity_name: '主机总成',
        entity_version: 'A',
        action: 'upgrade',
        status: 'pending',
        sort_order: 3,
      },
    ],
  },
  {
    id: 'eco-2',
    eco_number: 'ECO-2026-002',
    title: '执行：螺栓材质变更为不锈钢304',
    description: '更换所有M8螺栓的材质和供应商信息。',
    reason: '关联 ECR-2026-001 审核中',
    priority: 'high',
    category: '材料变更',
    status: 'draft',
    review_mode: 'all',
    creator_id: 'u-prod',
    creator_name: '李工',
    reviewers,
    reviewers_count: 2,
    approved_count: 0,
    execution_count: 0,
    execution_completed_count: 0,
    document_links: [],
    ecr_id: 'ecr-1',
    ecr_number: 'ECR-2026-001',
    created_at: '2026-06-29T09:00:00Z',
    updated_at: '2026-06-29T09:00:00Z',
  },
  {
    id: 'eco-3',
    eco_number: 'ECO-2026-003',
    title: '执行：取消出口型选装件',
    description: '从出口型BOM中移除部分选装泵组件。',
    reason: '关联 ECR-2026-004 已关闭',
    priority: 'low',
    category: '配置变更',
    status: 'completed',
    review_mode: 'all',
    creator_id: 'u-admin',
    creator_name: '系统管理员',
    reviewers,
    reviewers_count: 2,
    approved_count: 2,
    execution_count: 2,
    execution_completed_count: 2,
    document_links: [],
    ecr_id: 'ecr-4',
    ecr_number: 'ECR-2026-004',
    created_at: '2026-06-20T10:00:00Z',
    updated_at: '2026-06-25T16:00:00Z',
    executed_at: '2026-06-25T16:00:00Z',
  },
];

function makeEcrDetail(id: string) {
  const ecr = ecrList.find((e) => e.id === id);
  if (!ecr) return null;
  return {
    ...ecr,
    affected_items: [],
    review_records: ecr.status !== 'draft'
      ? [
          {
            id: 'rr-1',
            reviewer_id: 'u-admin',
            reviewer_name: '系统管理员',
            decision: 'approved' as const,
            comment: '同意变更，请按流程执行。',
            created_at: '2026-06-29T10:00:00Z',
          },
        ]
      : [],
    status_logs: [
      { id: 'sl-1', from_status: '', to_status: 'draft', operator_name: ecr.creator_name, created_at: ecr.created_at },
      ...(ecr.status !== 'draft'
        ? [{ id: 'sl-2', from_status: 'draft', to_status: ecr.status, operator_name: ecr.creator_name, comment: '', created_at: ecr.updated_at }]
        : []),
    ],
  };
}

function makeEcoDetail(id: string) {
  const eco = ecoList.find((e) => e.id === id);
  if (!eco) return null;
  return {
    ...eco,
    review_records: eco.status !== 'draft'
      ? [{ id: 'rr-1', reviewer_id: 'u-admin', reviewer_name: '系统管理员', decision: 'approved' as const, created_at: now }]
      : [],
    status_logs: [
      { id: 'sl-1', from_status: '', to_status: 'draft', operator_name: eco.creator_name, created_at: eco.created_at },
      ...(eco.status !== 'draft'
        ? [{ id: 'sl-2', from_status: 'draft', to_status: eco.status, operator_name: eco.creator_name, comment: '', created_at: now }]
        : []),
    ],
  };
}

export const changemgmtRoutes: MockRoute[] = [
  {
    method: 'get',
    pattern: /^\/ecrs\/$/,
    handler: ({ query }) => {
      const s = (query.get('search') || '').trim();
      const status = query.get('status') || '';
      const priority = query.get('priority') || '';
      let items = ecrList;
      if (s) items = items.filter((e) => e.ecr_number.includes(s) || e.title.includes(s));
      if (status) items = items.filter((e) => e.status === status);
      if (priority) items = items.filter((e) => e.priority === priority);
      return { items, total: items.length };
    },
  },
  {
    method: 'get',
    pattern: /^\/ecrs\/([^/]+)$/,
    keys: ['id'],
    handler: ({ params }) => makeEcrDetail(params.id) || null,
  },
  {
    method: 'post',
    pattern: /^\/ecrs\/$/,
    handler: ({ body }) => ({
      id: `ecr-new-${Date.now()}`,
      ecr_number: `ECR-2026-${String(ecrList.length + 1).padStart(3, '0')}`,
      ...body,
      status: 'draft',
      creator_id: 'u-admin',
      creator_name: '系统管理员',
      reviewers_count: (body?.reviewers || []).length,
      approved_count: 0,
      affected_count: 0,
      document_links: [],
      created_at: now,
      updated_at: now,
    }),
  },
  {
    method: 'put',
    pattern: /^\/ecrs\/([^/]+)$/,
    keys: ['id'],
    handler: ({ params, body }) => ({ ...ecrList.find((e) => e.id === params.id), ...body, updated_at: now }),
  },
  {
    method: 'delete',
    pattern: /^\/ecrs\/([^/]+)$/,
    keys: ['id'],
    handler: () => ({ message: '已删除' }),
  },
  { method: 'post', pattern: /^\/ecrs\/([^/]+)\/submit$/, handler: () => ({ message: '已提交审核' }) },
  { method: 'post', pattern: /^\/ecrs\/([^/]+)\/withdraw$/, handler: () => ({ message: '已撤回' }) },
  { method: 'post', pattern: /^\/ecrs\/([^/]+)\/close$/, handler: () => ({ message: '已关闭' }) },
  { method: 'post', pattern: /^\/ecrs\/([^/]+)\/review$/, handler: () => ({ message: '审核完成' }) },
  {
    method: 'get',
    pattern: /^\/ecrs\/([^/]+)\/status-logs$/,
    keys: ['id'],
    handler: ({ params }) => {
      const detail = makeEcrDetail(params.id);
      return detail ? detail.status_logs : [];
    },
  },
  { method: 'post', pattern: /^\/ecrs\/([^/]+)\/affected-items$/, handler: ({ body }) => ({ id: `ai-${Date.now()}`, ...body }) },
  { method: 'delete', pattern: /^\/ecrs\/([^/]+)\/affected-items\/([^/]+)$/, handler: () => ({ message: '已移除' }) },
  { method: 'post', pattern: /^\/ecrs\/([^/]+)\/bom-trace\/([^/]+)\/([^/]+)$/, handler: () => ({ data: [] }) },
  { method: 'post', pattern: /^\/ecrs\/([^/]+)\/cc$/, handler: () => ({ message: '已添加抄送' }) },
  { method: 'delete', pattern: /^\/ecrs\/([^/]+)\/cc\/([^/]+)$/, handler: () => ({ message: '已移除抄送' }) },

  // ECO routes
  {
    method: 'get',
    pattern: /^\/ecos\/$/,
    handler: ({ query }) => {
      const s = (query.get('search') || '').trim();
      const status = query.get('status') || '';
      const priority = query.get('priority') || '';
      let items = ecoList;
      if (s) items = items.filter((e) => e.eco_number.includes(s) || e.title.includes(s));
      if (status) items = items.filter((e) => e.status === status);
      if (priority) items = items.filter((e) => e.priority === priority);
      return { items, total: items.length };
    },
  },
  {
    method: 'get',
    pattern: /^\/ecos\/([^/]+)$/,
    keys: ['id'],
    handler: ({ params }) => makeEcoDetail(params.id) || null,
  },
  {
    method: 'post',
    pattern: /^\/ecos\/$/,
    handler: ({ body }) => ({
      id: `eco-new-${Date.now()}`,
      eco_number: `ECO-2026-${String(ecoList.length + 1).padStart(3, '0')}`,
      ...body,
      status: 'draft',
      creator_id: 'u-admin',
      creator_name: '系统管理员',
      reviewers_count: (body?.reviewers || []).length,
      approved_count: 0,
      execution_count: (body?.execution_items || []).length,
      execution_completed_count: 0,
      document_links: [],
      created_at: now,
      updated_at: now,
    }),
  },
  {
    method: 'put',
    pattern: /^\/ecos\/([^/]+)$/,
    keys: ['id'],
    handler: ({ params, body }) => ({ ...ecoList.find((e) => e.id === params.id), ...body, updated_at: now }),
  },
  {
    method: 'delete',
    pattern: /^\/ecos\/([^/]+)$/,
    keys: ['id'],
    handler: () => ({ message: '已删除' }),
  },
  { method: 'post', pattern: /^\/ecos\/([^/]+)\/submit$/, handler: () => ({ message: '已提交审核' }) },
  { method: 'post', pattern: /^\/ecos\/([^/]+)\/withdraw$/, handler: () => ({ message: '已撤回' }) },
  { method: 'post', pattern: /^\/ecos\/([^/]+)\/close$/, handler: () => ({ message: '已关闭' }) },
  { method: 'post', pattern: /^\/ecos\/([^/]+)\/review$/, handler: () => ({ message: '审核完成' }) },
  { method: 'post', pattern: /^\/ecos\/([^/]+)\/complete$/, handler: () => ({ message: '执行完成' }) },
  { method: 'post', pattern: /^\/ecos\/([^/]+)\/execute$/, handler: () => ({ message: '已开始执行' }) },
  { method: 'post', pattern: /^\/ecos\/([^/]+)\/execute-all$/, handler: () => ({ message: '全部已执行' }) },
  { method: 'post', pattern: /^\/ecos\/([^/]+)\/execute-item\/([^/]+)$/, handler: () => ({ message: '已执行' }) },
  {
    method: 'get',
    pattern: /^\/ecos\/([^/]+)\/execution-items$/,
    keys: ['id'],
    handler: ({ params }) => {
      const eco = ecoList.find((e) => e.id === params.id);
      return { items: eco?.execution_items || [], total: (eco?.execution_items || []).length };
    },
  },
  {
    method: 'post',
    pattern: /^\/ecos\/([^/]+)\/execution-items$/,
    handler: ({ body }) => ({ id: `ei-${Date.now()}`, ...body, status: 'pending', sort_order: 99 }),
  },
  {
    method: 'put',
    pattern: /^\/ecos\/([^/]+)\/execution-items\/([^/]+)$/,
    handler: ({ params, body }) => ({ ...body, id: params[1], updated_at: now }),
  },
  {
    method: 'delete',
    pattern: /^\/ecos\/([^/]+)\/execution-items\/([^/]+)$/,
    handler: () => ({ message: '已删除执行项' }),
  },
  {
    method: 'post',
    pattern: /^\/ecos\/([^/]+)\/execution-items\/([^/]+)\/(upgrade|release|freeze|revert)$/,
    handler: ({ params }) => ({ message: `已执行${params[2]}`, new_version: 'B' }),
  },
  {
    method: 'post',
    pattern: /^\/ecos\/([^/]+)\/release-items\/publish-all$/,
    handler: () => ({ message: '发布完成' }),
  },
  {
    method: 'get',
    pattern: /^\/ecos\/([^/]+)\/release-items\/publish-status$/,
    handler: () => ({ status: 'completed' }),
  },
  {
    method: 'get',
    pattern: /^\/ecos\/([^/]+)\/status-logs$/,
    keys: ['id'],
    handler: ({ params }) => {
      const detail = makeEcoDetail(params.id);
      return (detail as any)?.status_logs || [];
    },
  },
  { method: 'post', pattern: /^\/ecos\/([^/]+)\/cc$/, handler: () => ({ message: '已添加抄送' }) },
  { method: 'delete', pattern: /^\/ecos\/([^/]+)\/cc\/([^/]+)$/, handler: () => ({ message: '已移除抄送' }) },
  { method: 'post', pattern: /^\/ecos\/([^/]+)\/bom-trace\/([^/]+)\/([^/]+)$/, handler: () => ({ data: [] }) },
];
