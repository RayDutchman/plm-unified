import type { MockRoute } from '../types';

const now = new Date().toISOString();

const docs = [
  {
    id: 'doc-1', code: 'DOC-001', name: '主机总成装配图', version: 'B',
    status: 'released' as const, remark: '修订版：增加密封圈标注',
    file_name: '主机总成装配图_vB.dwg', file_id: 'fid-001',
    creator_id: 'u-eng', creator_name: '张工',
    accessible: true, group_ids: ['ug-1', 'ug-2'],
    created_at: '2026-06-01T00:00:00Z', updated_at: '2026-06-25T00:00:00Z',
  },
  {
    id: 'doc-2', code: 'DOC-002', name: '支架零件图', version: 'A',
    status: 'draft' as const, remark: '初版设计，待审核',
    file_name: '支架_SPCC2mm.dwg', file_id: 'fid-002',
    creator_id: 'u-eng', creator_name: '张工',
    accessible: true, group_ids: ['ug-2'],
    created_at: '2026-06-20T00:00:00Z', updated_at: '2026-06-20T00:00:00Z',
  },
  {
    id: 'doc-3', code: 'DOC-003', name: '产品规格书', version: 'C',
    status: 'frozen' as const, remark: '送审冻结版本，封存待归档',
    file_name: '产品规格书_vC.pdf', file_id: 'fid-003',
    creator_id: 'u-admin', creator_name: '系统管理员',
    accessible: true, group_ids: ['ug-1'],
    created_at: '2026-05-15T00:00:00Z', updated_at: '2026-06-10T00:00:00Z',
  },
  {
    id: 'doc-4', code: 'DOC-004', name: '测试报告(废弃)', version: 'A',
    status: 'obsolete' as const, remark: '已由 DOC-005 替代',
    file_name: '测试报告_2026Q1.pdf', file_id: 'fid-004',
    creator_id: 'u-prod', creator_name: '李工',
    accessible: false, group_ids: [],
    created_at: '2026-01-10T00:00:00Z', updated_at: '2026-03-01T00:00:00Z',
  },
];

const attachments = [
  { id: 'att-1', document_id: 'doc-1', file_name: '主机总成装配图_vB.dwg', file_size: 2457600, created_at: '2026-06-25T00:00:00Z' },
  { id: 'att-2', document_id: 'doc-2', file_name: '支架_SPCC2mm.dwg', file_size: 1024000, created_at: '2026-06-20T00:00:00Z' },
  { id: 'att-3', document_id: 'doc-3', file_name: '产品规格书_vC.pdf', file_size: 3072000, created_at: '2026-06-10T00:00:00Z' },
];

export const documentsFixtureRoutes: MockRoute[] = [
  {
    method: 'get',
    pattern: /^\/documents\/$/,
    handler: ({ query }) => {
      const s = (query.get('keyword') || query.get('search') || '').trim();
      const status = query.get('status') || '';
      let items = docs;
      if (s) items = items.filter((d) => d.code.includes(s) || d.name.includes(s));
      if (status) items = items.filter((d) => d.status === status);
      return { items, total: items.length };
    },
  },
  {
    method: 'get',
    pattern: /^\/documents\/([^/]+)$/,
    keys: ['id'],
    handler: ({ params }) => docs.find((d) => d.id === params.id) || null,
  },
  {
    method: 'post',
    pattern: /^\/documents\/$/,
    handler: ({ body }) => ({
      id: `doc-${Date.now()}`, code: body?.code || `DOC-${String(docs.length + 1).padStart(3, '0')}`,
      name: body?.name || '', version: body?.version || 'A',
      status: body?.status || 'draft', remark: body?.remark || '',
      creator_id: 'u-admin', creator_name: '系统管理员',
      group_ids: body?.group_ids || [],
      created_at: now, updated_at: now,
    }),
  },
  {
    method: 'put',
    pattern: /^\/documents\/([^/]+)$/,
    keys: ['id'],
    handler: ({ params, body }) => ({ ...docs.find((d) => d.id === params.id), ...body, updated_at: now }),
  },
  {
    method: 'delete',
    pattern: /^\/documents\/([^/]+)$/,
    keys: ['id'],
    handler: () => ({ message: '已删除' }),
  },
  {
    method: 'post',
    pattern: /^\/documents\/([^/]+)\/upgrade$/,
    handler: ({ body }) => ({ id: `doc-${Date.now()}`, version: 'B', status: 'draft', created_at: now, ...body }),
  },
  {
    method: 'get',
    pattern: /^\/documents\/([^/]+)\/versions$/,
    keys: ['id'],
    handler: ({ params }) => {
      const doc = docs.find((d) => d.id === params.id);
      if (!doc) return [];
      return [
        { ...doc, version: 'A', status: 'obsolete', file_name: doc.file_name?.replace('_v' + doc.version, '_vA'), created_at: doc.created_at, updated_at: doc.created_at },
        doc,
      ];
    },
  },
  {
    method: 'get',
    pattern: /^\/documents\/([^/]+)\/attachments\/$/,
    keys: ['id'],
    handler: ({ params }) => ({ items: attachments.filter((a) => a.document_id === params.id), total: attachments.filter((a) => a.document_id === params.id).length }),
  },
  {
    method: 'get',
    pattern: /^\/documents\/([^/]+)\/attachments\/([^/]+)$/,
    handler: ({ params }) => attachments.find((a) => a.id === params[1]) || null,
  },
  {
    method: 'post',
    pattern: /^\/documents\/([^/]+)\/attachments$/,
    handler: ({ body }) => ({ id: `att-${Date.now()}`, document_id: body?.document_id, file_name: body?.file_name, created_at: now }),
  },
  {
    method: 'delete',
    pattern: /^\/documents\/([^/]+)\/attachments\/([^/]+)$/,
    handler: () => ({ message: '已删除附件' }),
  },
  {
    method: 'get',
    pattern: /^\/documents\/([^/]+)\/references$/,
    handler: () => ({
      parts: [{ id: 'pm-001', code: 'P-001', name: '螺栓 M8×30' }],
      assemblies: [{ id: 'pm-100', code: 'ASM-100', name: '泵组件' }],
      boards: [],
    }),
  },
];
