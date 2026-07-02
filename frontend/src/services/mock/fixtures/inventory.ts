import type { MockRoute } from '../types';

const warehouses = [
  { id: 'wh-1', code: 'WH-MAIN', name: '主仓库', type: '普通仓', default_keeper_id: 'u-admin', status: 'active', remark: '生产用主仓库' },
  { id: 'wh-2', code: 'WH-LINE', name: '线边仓', type: '线边仓', default_keeper_id: 'u-prod', status: 'active', remark: '生产线边暂存' },
];

const materials = [
  { id: 'mat-1', code: 'M-001', name: '螺栓 M8×30', spec: '不锈钢304', unit: 'ea', source_type: 'part', ref_entity_type: 'part', ref_entity_id: 'pm-001', track_mode: 'quantity', safety_stock: 100, status: 'active' },
  { id: 'mat-2', code: 'M-002', name: '支架', spec: 'SPCC 2mm', unit: 'ea', source_type: 'part', ref_entity_type: 'part', ref_entity_id: 'pm-002', track_mode: 'quantity', safety_stock: 20, status: 'active' },
  { id: 'mat-3', code: 'M-003', name: '密封圈', spec: 'NBR φ50×3.5', unit: 'ea', source_type: 'standalone', track_mode: 'quantity', safety_stock: 50, status: 'active' },
  { id: 'mat-4', code: 'M-004', name: '润滑油', spec: 'ISO VG46', unit: 'L', source_type: 'standalone', track_mode: 'batch', safety_stock: 10, status: 'active' },
];

const stock = [
  { material_id: 'mat-1', material_code: 'M-001', material_name: '螺栓 M8×30', unit: 'ea', warehouse_id: 'wh-1', batch_no: 'B20260620', quantity: 350, safety_stock: 100, is_low: false },
  { material_id: 'mat-1', material_code: 'M-001', material_name: '螺栓 M8×30', unit: 'ea', warehouse_id: 'wh-2', batch_no: 'B20260620', quantity: 30, safety_stock: 100, is_low: true },
  { material_id: 'mat-2', material_code: 'M-002', material_name: '支架', unit: 'ea', warehouse_id: 'wh-1', batch_no: 'B20260625', quantity: 45, safety_stock: 20, is_low: false },
  { material_id: 'mat-3', material_code: 'M-003', material_name: '密封圈', unit: 'ea', warehouse_id: 'wh-1', batch_no: 'B20260610', quantity: 5, safety_stock: 50, is_low: true },
  { material_id: 'mat-4', material_code: 'M-004', material_name: '润滑油', unit: 'L', warehouse_id: 'wh-1', batch_no: 'L20260615', quantity: 25, safety_stock: 10, is_low: false },
];

const invDocs = [
  {
    id: 'idoc-1', doc_number: 'INV-2026-001', doc_type: 'inbound', biz_type: '采购入库',
    status: 'posted', warehouse_id: 'wh-1', keeper_id: 'u-admin', keeper_name: '系统管理员',
    creator_id: 'u-eng', creator_name: '张工', remark: '螺栓到货',
    lines: [{ material_id: 'mat-1', batch_no: 'B20260620', quantity: 500, direction: 'in' }],
    created_at: '2026-06-20T08:00:00Z', updated_at: '2026-06-20T10:00:00Z',
  },
  {
    id: 'idoc-2', doc_number: 'INV-2026-002', doc_type: 'outbound', biz_type: '生产领料',
    status: 'approved', warehouse_id: 'wh-1', keeper_id: 'u-admin', keeper_name: '系统管理员',
    creator_id: 'u-prod', creator_name: '李工', remark: '泵组件生产用料',
    lines: [
      { material_id: 'mat-1', batch_no: 'B20260620', quantity: 150, direction: 'out' },
      { material_id: 'mat-2', batch_no: 'B20260625', quantity: 5, direction: 'out' },
    ],
    created_at: '2026-06-28T09:00:00Z', updated_at: '2026-06-28T09:00:00Z',
  },
  {
    id: 'idoc-3', doc_number: 'INV-2026-003', doc_type: 'transfer', biz_type: '库间调拨',
    status: 'draft', warehouse_id: 'wh-1', to_warehouse_id: 'wh-2',
    creator_id: 'u-admin', creator_name: '系统管理员', remark: '线边仓补货',
    lines: [{ material_id: 'mat-1', batch_no: 'B20260620', quantity: 100 }],
    created_at: '2026-06-29T08:00:00Z', updated_at: '2026-06-29T08:00:00Z',
  },
  {
    id: 'idoc-4', doc_number: 'INV-2026-004', doc_type: 'stocktake',
    status: 'reviewing', warehouse_id: 'wh-1',
    creator_id: 'u-prod', creator_name: '李工', remark: '月度盘点',
    lines: [
      { material_id: 'mat-3', batch_no: 'B20260610', quantity: 5, counted_quantity: 5 },
      { material_id: 'mat-4', batch_no: 'L20260615', quantity: 25, counted_quantity: 24 },
    ],
    created_at: '2026-06-30T07:00:00Z', updated_at: '2026-06-30T07:00:00Z',
  },
];

const ledger = [
  { id: 'led-1', doc_id: 'idoc-1', doc_number: 'INV-2026-001', doc_type: 'inbound', material_id: 'mat-1', material_code: 'M-001', material_name: '螺栓 M8×30', warehouse_id: 'wh-1', batch_no: 'B20260620', direction: 'in', quantity: 500, balance: 500, created_at: '2026-06-20T10:00:00Z' },
  { id: 'led-2', doc_id: 'idoc-2', doc_number: 'INV-2026-002', doc_type: 'outbound', material_id: 'mat-1', material_code: 'M-001', material_name: '螺栓 M8×30', warehouse_id: 'wh-1', batch_no: 'B20260620', direction: 'out', quantity: 150, balance: 350, created_at: '2026-06-28T09:00:00Z' },
];

export const inventoryRoutes: MockRoute[] = [
  // 仓库
  {
    method: 'get',
    pattern: /^\/warehouses$/,
    handler: () => ({ items: warehouses, total: warehouses.length }),
  },
  {
    method: 'post',
    pattern: /^\/warehouses$/,
    handler: ({ body }) => ({ id: `wh-${Date.now()}`, ...body, status: 'active' }),
  },
  { method: 'put', pattern: /^\/warehouses\/([^/]+)$/, handler: ({ params, body }) => ({ ...warehouses.find((w) => w.id === params[0]), ...body }) },
  { method: 'delete', pattern: /^\/warehouses\/([^/]+)$/, handler: () => ({ message: '已删除' }) },

  // 物料
  {
    method: 'get',
    pattern: /^\/materials$/,
    handler: ({ query }) => {
      const s = (query.get('search') || '').trim();
      const sourceType = query.get('source_type') || '';
      let items = materials;
      if (s) items = items.filter((m) => m.code.includes(s) || m.name.includes(s));
      if (sourceType) items = items.filter((m) => m.source_type === sourceType);
      return { items, total: items.length };
    },
  },
  { method: 'post', pattern: /^\/materials$/, handler: ({ body }) => ({ id: `mat-${Date.now()}`, ...body, status: 'active' }) },
  { method: 'post', pattern: /^\/materials\/enable-from-pdm$/, handler: ({ body }) => ({ id: `mat-${Date.now()}`, ...body, source_type: 'part', status: 'active' }) },
  { method: 'put', pattern: /^\/materials\/([^/]+)$/, handler: ({ params, body }) => ({ ...materials.find((m) => m.id === params[0]), ...body }) },
  { method: 'delete', pattern: /^\/materials\/([^/]+)$/, handler: () => ({ message: '已删除' }) },

  // 库存
  {
    method: 'get',
    pattern: /^\/stock$/,
    handler: ({ query }) => {
      const materialId = query.get('material') || '';
      const warehouseId = query.get('warehouse_id') || '';
      const lowOnly = query.get('low_only') === 'true';
      let items = stock;
      if (materialId) items = items.filter((s) => s.material_id === materialId);
      if (warehouseId) items = items.filter((s) => s.warehouse_id === warehouseId);
      if (lowOnly) items = items.filter((s) => s.is_low);
      return { items, total: items.length };
    },
  },
  {
    method: 'get',
    pattern: /^\/stock\/ledger$/,
    handler: ({ query }) => {
      const materialId = query.get('material_id') || '';
      let items = ledger;
      if (materialId) items = items.filter((l: any) => l.material_id === materialId);
      return { items, total: items.length };
    },
  },

  // 单据
  {
    method: 'get',
    pattern: /^\/documents$/,
    handler: ({ query }) => {
      const s = (query.get('search') || '').trim();
      const docType = query.get('doc_type') || '';
      const status = query.get('status') || '';
      let items = invDocs;
      if (s) items = items.filter((d) => d.doc_number.includes(s) || d.remark?.includes(s));
      if (docType) items = items.filter((d) => d.doc_type === docType);
      if (status) items = items.filter((d) => d.status === status);
      return { items, total: items.length };
    },
  },
  {
    method: 'get',
    pattern: /^\/documents\/([^/]+)$/,
    keys: ['id'],
    handler: ({ params }) => invDocs.find((d) => d.id === params.id) || null,
  },
  {
    method: 'post',
    pattern: /^\/documents$/,
    handler: ({ body }) => ({
      id: `idoc-${Date.now()}`,
      doc_number: `INV-2026-${String(invDocs.length + 1).padStart(3, '0')}`,
      ...body,
      status: 'draft',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }),
  },
  { method: 'put', pattern: /^\/documents\/([^/]+)$/, handler: ({ params, body }) => ({ ...invDocs.find((d) => d.id === params[0]), ...body, updated_at: new Date().toISOString() }) },
  { method: 'delete', pattern: /^\/documents\/([^/]+)$/, handler: () => ({ message: '已删除' }) },
  { method: 'post', pattern: /^\/documents\/([^/]+)\/submit$/, handler: () => ({ message: '已提交' }) },
  { method: 'post', pattern: /^\/documents\/([^/]+)\/withdraw$/, handler: () => ({ message: '已撤回' }) },
  { method: 'post', pattern: /^\/documents\/([^/]+)\/review$/, handler: () => ({ message: '审核完成' }) },
  { method: 'post', pattern: /^\/documents\/([^/]+)\/assign-keeper$/, handler: () => ({ message: '已分配保管人' }) },
  { method: 'post', pattern: /^\/documents\/([^/]+)\/post$/, handler: () => ({ message: '已过账' }) },
  { method: 'post', pattern: /^\/documents\/([^/]+)\/cancel$/, handler: () => ({ message: '已作废' }) },
];
