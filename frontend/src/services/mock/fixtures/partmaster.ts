import type { MockRoute } from '../types';

// 统一 PartMaster 假数据：2 个叶子零件 + 2 个装配体（含子件）。
// 字段对齐 M1.4 后端 schema：PartMaster / PartRevision / PartUsageLink。
interface Master {
  id: string;
  number: string;
  name: string;
  type: string;
  standard_part: boolean;
  latest_version: string;
  status: 'WIP' | 'RELEASED' | 'OBSOLETE';
  checkout_user: string | null;
  revisions: { version: string; status: string; iterations: { iteration: number; iteration_note?: string; check_in_date?: string | null }[] }[];
  usage_links: { component_number: string; component_name: string; amount: number; unit: string }[];
}

const masters: Master[] = [
  {
    id: 'pm-001', number: 'P-001', name: '螺栓 M8×30', type: '标准件', standard_part: true,
    latest_version: 'B', status: 'RELEASED', checkout_user: null,
    revisions: [
      { version: 'A', status: 'OBSOLETE', iterations: [{ iteration: 1, check_in_date: '2026-05-01T00:00:00Z' }] },
      { version: 'B', status: 'RELEASED', iterations: [{ iteration: 1, iteration_note: '材料改为不锈钢 304', check_in_date: '2026-06-01T00:00:00Z' }] },
    ],
    usage_links: [],
  },
  {
    id: 'pm-002', number: 'P-002', name: '支架', type: '钣金件', standard_part: false,
    latest_version: 'A', status: 'WIP', checkout_user: null,
    revisions: [{ version: 'A', status: 'WIP', iterations: [{ iteration: 1, check_in_date: null }] }],
    usage_links: [],
  },
  {
    id: 'pm-100', number: 'ASM-100', name: '泵组件', type: '装配体', standard_part: false,
    latest_version: 'A', status: 'RELEASED', checkout_user: null,
    revisions: [{ version: 'A', status: 'RELEASED', iterations: [{ iteration: 2, iteration_note: '增加密封圈', check_in_date: '2026-06-10T00:00:00Z' }] }],
    usage_links: [
      { component_number: 'P-001', component_name: '螺栓 M8×30', amount: 4, unit: 'ea' },
      { component_number: 'P-002', component_name: '支架', amount: 1, unit: 'ea' },
    ],
  },
  {
    id: 'pm-200', number: 'ASM-200', name: '主机总成', type: '装配体', standard_part: false,
    latest_version: 'A', status: 'WIP', checkout_user: '张工',
    revisions: [{ version: 'A', status: 'WIP', iterations: [{ iteration: 1, check_in_date: null }] }],
    usage_links: [
      { component_number: 'ASM-100', component_name: '泵组件', amount: 2, unit: 'ea' },
      { component_number: 'P-002', component_name: '支架', amount: 3, unit: 'ea' },
    ],
  },
];

const toListItem = (m: Master) => ({
  id: m.id, number: m.number, name: m.name, type: m.type, standard_part: m.standard_part,
  latest_version: m.latest_version, status: m.status, checkout_user: m.checkout_user,
  is_assembly: m.usage_links.length > 0, child_count: m.usage_links.length,
});

export const partMasterRoutes: MockRoute[] = [
  {
    method: 'get',
    pattern: /^\/parts$/,
    handler: ({ query }) => {
      const s = (query.get('search') || '').trim();
      const items = masters.filter((m) => !s || m.number.includes(s) || m.name.includes(s)).map(toListItem);
      return { items, total: items.length };
    },
  },
  {
    method: 'get',
    pattern: /^\/parts\/([^/]+)$/,
    keys: ['number'],
    handler: ({ params }) => {
      const m = masters.find((x) => x.number === decodeURIComponent(params.number));
      return m ? { ...toListItem(m), revisions: m.revisions, usage_links: m.usage_links } : null;
    },
  },
];
