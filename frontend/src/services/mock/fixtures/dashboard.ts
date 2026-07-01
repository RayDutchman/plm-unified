import type { MockRoute } from '../types';

// 仪表盘统计（字段名以 Dashboard.tsx 实际解构为准，Task 1.1 校正）
const stats = {
  parts: 128,
  assemblies: 32,
  documents: 240,
  ecr_open: 5,
  eco_open: 3,
  inventory_low: 7,
};

export const dashboardRoutes: MockRoute[] = [
  { method: 'get', pattern: /^\/dashboard\/stats$/, handler: () => stats },
];
