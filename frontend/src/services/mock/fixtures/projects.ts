import type { MockRoute } from '../types';

const now = new Date().toISOString();

interface ProjMember {
  id: string; user_id: string; user_name: string; username: string; role_in_project: '经理' | '成员';
}
interface Proj {
  id: string; code: string; name: string; status: string;
  owner_id: string; owner_name: string; planned_start: string | null; planned_end: string | null;
  description: string | null; member_count: number; members: ProjMember[]; created_at: string;
}
interface ProjTask {
  id: string; project_id: string; parent_id: string | null; code: string; name: string;
  task_type: string; assignee_id: string | null; assignee_name: string | null;
  status: string; priority: string;
  planned_start: string | null; planned_end: string | null;
  sort_order: number; description: string | null; link_count: number; children: ProjTask[];
}

const members_1: ProjMember[] = [
  { id: 'mem-1', user_id: 'u-admin', user_name: '系统管理员', username: 'admin', role_in_project: '经理' },
  { id: 'mem-2', user_id: 'u-eng', user_name: '张工', username: 'engineer', role_in_project: '成员' },
  { id: 'mem-3', user_id: 'u-prod', user_name: '李工', username: 'prod', role_in_project: '成员' },
];

const members_2: ProjMember[] = [
  { id: 'mem-4', user_id: 'u-eng', user_name: '张工', username: 'engineer', role_in_project: '经理' },
  { id: 'mem-5', user_id: 'u-prod', user_name: '李工', username: 'prod', role_in_project: '成员' },
];

const projects: Proj[] = [
  {
    id: 'proj-1', code: 'PRJ-2026-001', name: '主机总成 V2.0 研发', status: '进行中',
    owner_id: 'u-admin', owner_name: '系统管理员',
    planned_start: '2026-06-01', planned_end: '2026-09-30',
    description: '新一代主机总成研发项目，涵盖结构优化、材料升级和工艺改进。',
    member_count: 3, members: members_1, created_at: '2026-05-20T00:00:00Z',
  },
  {
    id: 'proj-2', code: 'PRJ-2026-002', name: '泵组件国产化替代', status: '进行中',
    owner_id: 'u-eng', owner_name: '张工',
    planned_start: '2026-07-01', planned_end: '2026-12-31',
    description: '泵组件关键零件国产化替代方案验证与实施。',
    member_count: 2, members: members_2, created_at: '2026-06-15T00:00:00Z',
  },
  {
    id: 'proj-3', code: 'PRJ-2026-003', name: '出口型认证合规改进', status: '待启动',
    owner_id: 'u-admin', owner_name: '系统管理员',
    planned_start: '2026-08-01', planned_end: '2026-10-31',
    description: null, member_count: 0, members: [],
    created_at: '2026-06-28T00:00:00Z',
  },
  {
    id: 'proj-4', code: 'PRJ-2025-Q4', name: '2025Q4 质量改进专项', status: '已完成',
    owner_id: 'u-admin', owner_name: '系统管理员',
    planned_start: '2025-10-01', planned_end: '2025-12-31',
    description: 'Q4质量改进专项，已完成全部整改项。',
    member_count: 2, members: members_1.slice(0, 2),
    created_at: '2025-09-20T00:00:00Z',
  },
  {
    id: 'proj-5', code: 'PRJ-2025-Q3', name: 'Q3 工艺优化', status: '已归档',
    owner_id: 'u-eng', owner_name: '张工',
    planned_start: '2025-07-01', planned_end: '2025-09-30',
    description: null, member_count: 1, members: members_2.slice(0, 1),
    created_at: '2025-06-20T00:00:00Z',
  },
];

const tasks: Record<string, ProjTask[]> = {
  'proj-1': [
    {
      id: 'task-1', project_id: 'proj-1', parent_id: null, code: 'T1',
      name: '需求分析', task_type: '任务',
      assignee_id: 'u-eng', assignee_name: '张工',
      status: '已完成', priority: '高',
      planned_start: '2026-06-01', planned_end: '2026-06-15',
      sort_order: 1, description: '收集并整理客户需求文档', link_count: 2, children: [],
    },
    {
      id: 'task-2', project_id: 'proj-1', parent_id: null, code: 'T2',
      name: '方案设计', task_type: '任务',
      assignee_id: 'u-eng', assignee_name: '张工',
      status: '进行中', priority: '高',
      planned_start: '2026-06-16', planned_end: '2026-07-15',
      sort_order: 2, description: null, link_count: 1, children: [],
    },
    {
      id: 'task-3', project_id: 'proj-1', parent_id: 'task-2', code: 'T2.1',
      name: '结构方案评审', task_type: '评审',
      assignee_id: 'u-admin', assignee_name: '系统管理员',
      status: '未开始', priority: '中',
      planned_start: '2026-07-01', planned_end: '2026-07-05',
      sort_order: 1, description: '组织评审会', link_count: 0, children: [],
    },
    {
      id: 'task-4', project_id: 'proj-1', parent_id: null, code: 'M1',
      name: '设计冻结里程碑', task_type: '里程碑',
      assignee_id: null, assignee_name: null,
      status: '未开始', priority: '高',
      planned_start: '2026-07-15', planned_end: '2026-07-15',
      sort_order: 3, description: null, link_count: 0, children: [],
    },
    {
      id: 'task-5', project_id: 'proj-1', parent_id: null, code: 'T3',
      name: '样品试制', task_type: '任务',
      assignee_id: 'u-prod', assignee_name: '李工',
      status: '未开始', priority: '中',
      planned_start: '2026-07-16', planned_end: '2026-08-15',
      sort_order: 4, description: null, link_count: 0, children: [],
    },
  ],
  'proj-2': [
    {
      id: 'task-6', project_id: 'proj-2', parent_id: null, code: 'T1',
      name: '供应商评估', task_type: '任务',
      assignee_id: 'u-prod', assignee_name: '李工',
      status: '未开始', priority: '高',
      planned_start: '2026-07-01', planned_end: '2026-07-20',
      sort_order: 1, description: '评估国内供应商能力', link_count: 0, children: [],
    },
    {
      id: 'task-7', project_id: 'proj-2', parent_id: null, code: 'T2',
      name: '样品测试', task_type: '任务',
      assignee_id: 'u-eng', assignee_name: '张工',
      status: '未开始', priority: '中',
      planned_start: '2026-07-21', planned_end: '2026-08-30',
      sort_order: 2, description: null, link_count: 0, children: [],
    },
  ],
};

const links = [
  { id: 'link-1', task_id: 'task-1', entity_type: 'document' as const, entity_id: 'doc-3', entity_code: 'DOC-003', entity_name: '产品规格书' },
  { id: 'link-2', task_id: 'task-1', entity_type: 'part' as const, entity_id: 'pm-001', entity_code: 'P-001', entity_name: '螺栓 M8×30' },
  { id: 'link-3', task_id: 'task-2', entity_type: 'assembly' as const, entity_id: 'pm-100', entity_code: 'ASM-100', entity_name: '泵组件' },
];

const comments = [
  { id: 'cmt-1', task_id: 'task-1', user_id: 'u-admin', user_name: '系统管理员', content: '需求文档已确认，可以进入方案设计阶段。', created_at: '2026-06-16T09:00:00Z' },
  { id: 'cmt-2', task_id: 'task-2', user_id: 'u-eng', user_name: '张工', content: '结构方案初稿已完成，请组织评审。', created_at: '2026-06-28T14:00:00Z' },
];

export const projectsFixtureRoutes: MockRoute[] = [
  {
    method: 'get',
    pattern: /^\/$/,
    handler: ({ query }) => {
      const s = (query.get('search') || '').trim();
      const status = query.get('status') || '';
      let items = projects;
      if (s) items = items.filter((p) => p.code.includes(s) || p.name.includes(s));
      if (status) items = items.filter((p) => p.status === status);
      return { items, total: items.length };
    },
  },
  {
    method: 'get',
    pattern: /^\/([^/]+)$/,
    keys: ['id'],
    handler: ({ params }) => projects.find((p) => p.id === params.id) || null,
  },
  {
    method: 'post',
    pattern: /^\/$/,
    handler: ({ body }) => ({
      id: `proj-${Date.now()}`, code: `PRJ-2026-${String(projects.length + 1).padStart(3, '0')}`,
      ...body, status: body?.status || '进行中',
      member_count: 0, members: [],
      created_at: now,
    }),
  },
  {
    method: 'put',
    pattern: /^\/([^/]+)$/,
    keys: ['id'],
    handler: ({ params, body }) => ({ ...projects.find((p) => p.id === params.id), ...body }),
  },
  {
    method: 'delete',
    pattern: /^\/([^/]+)$/,
    keys: ['id'],
    handler: () => ({ message: '已删除' }),
  },

  // Members
  {
    method: 'get',
    pattern: /^\/([^/]+)\/members$/,
    keys: ['id'],
    handler: ({ params }) => {
      const proj = projects.find((p) => p.id === params.id);
      return { items: proj?.members || [], total: proj?.members?.length || 0 };
    },
  },
  {
    method: 'post',
    pattern: /^\/([^/]+)\/members$/,
    handler: ({ body }) => ({ id: `mem-${Date.now()}`, ...body, role_in_project: body?.role_in_project || '成员' }),
  },
  {
    method: 'delete',
    pattern: /^\/([^/]+)\/members\/([^/]+)$/,
    handler: () => ({ message: '已移除成员' }),
  },

  // Tasks
  {
    method: 'get',
    pattern: /^\/([^/]+)\/tasks$/,
    keys: ['id'],
    handler: ({ params }) => {
      const items = tasks[params.id] || [];
      return { items, total: items.length };
    },
  },
  {
    method: 'post',
    pattern: /^\/([^/]+)\/tasks$/,
    handler: ({ params, body }) => ({
      id: `task-${Date.now()}`, project_id: params[0], parent_id: null,
      ...body, status: body?.status || '未开始', sort_order: body?.sort_order || 99,
      children: [], link_count: 0,
    }),
  },
  {
    method: 'put',
    pattern: /^\/([^/]+)\/tasks\/([^/]+)$/,
    handler: ({ params, body }) => {
      const allTasks = Object.values(tasks).flat();
      const t = allTasks.find((x) => x.id === params[1]);
      return { ...t, ...body };
    },
  },
  {
    method: 'patch',
    pattern: /^\/([^/]+)\/tasks\/([^/]+)\/status$/,
    handler: ({ body }) => ({ message: '状态已更新', status: body?.status }),
  },
  {
    method: 'post',
    pattern: /^\/([^/]+)\/tasks\/([^/]+)\/move$/,
    handler: ({ body }) => ({ message: '已移动', sort_order: body?.sort_order }),
  },
  {
    method: 'post',
    pattern: /^\/([^/]+)\/tasks\/reorder$/,
    handler: () => ({ message: '已排序' }),
  },
  {
    method: 'delete',
    pattern: /^\/([^/]+)\/tasks\/([^/]+)$/,
    handler: () => ({ message: '已删除任务' }),
  },

  // Task links
  {
    method: 'get',
    pattern: /^\/([^/]+)\/tasks\/([^/]+)\/links$/,
    handler: ({ params }) => {
      const taskLinks = links.filter((l) => l.task_id === params[1]);
      return { items: taskLinks, total: taskLinks.length };
    },
  },
  {
    method: 'post',
    pattern: /^\/([^/]+)\/tasks\/([^/]+)\/links$/,
    handler: ({ body }) => ({ id: `link-${Date.now()}`, ...body }),
  },
  {
    method: 'delete',
    pattern: /^\/([^/]+)\/tasks\/([^/]+)\/links\/([^/]+)$/,
    handler: () => ({ message: '已移除关联' }),
  },

  // Comments
  {
    method: 'get',
    pattern: /^\/([^/]+)\/tasks\/([^/]+)\/comments$/,
    handler: ({ params }) => {
      const taskComments = comments.filter((c) => c.task_id === params[1]);
      return { items: taskComments, total: taskComments.length };
    },
  },
  {
    method: 'post',
    pattern: /^\/([^/]+)\/tasks\/([^/]+)\/comments$/,
    handler: ({ body }) => ({
      id: `cmt-${Date.now()}`, user_id: 'u-admin', user_name: '系统管理员',
      ...body, created_at: now,
    }),
  },
  {
    method: 'delete',
    pattern: /^\/([^/]+)\/tasks\/([^/]+)\/comments\/([^/]+)$/,
    handler: () => ({ message: '已删除评论' }),
  },

  // Gantt / schedule / deps
  {
    method: 'get',
    pattern: /^\/([^/]+)\/gantt$/,
    handler: ({ params }) => {
      const projTasks = (tasks[params[0]] || []).map((t) => ({
        id: t.id, parent_id: t.parent_id, code: t.code, name: t.name,
        task_type: t.task_type, status: t.status, assignee_name: t.assignee_name,
        planned_start: t.planned_start, planned_end: t.planned_end,
        duration_days: t.planned_start && t.planned_end ? Math.ceil((new Date(t.planned_end).getTime() - new Date(t.planned_start).getTime()) / 86400000) : null,
        is_critical: false, is_overdue: false, sort_order: t.sort_order, depth: 0,
      }));
      return {
        tasks: projTasks, deps: [],
        range: { min_date: '2026-06-01', max_date: '2026-12-31' },
      };
    },
  },
  {
    method: 'post',
    pattern: /^\/([^/]+)\/auto-schedule$/,
    handler: () => ({ message: '自动排程完成' }),
  },
  {
    method: 'get',
    pattern: /^\/([^/]+)\/deps$/,
    handler: () => ({ items: [], total: 0 }),
  },
  {
    method: 'post',
    pattern: /^\/([^/]+)\/deps$/,
    handler: ({ body }) => ({ id: `dep-${Date.now()}`, ...body }),
  },
  {
    method: 'delete',
    pattern: /^\/([^/]+)\/deps\/([^/]+)$/,
    handler: () => ({ message: '已移除依赖' }),
  },
];
