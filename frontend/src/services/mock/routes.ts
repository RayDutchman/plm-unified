import type { MockRoute } from './types';
import { authRoutes } from './fixtures/auth';
import { shellRoutes } from './fixtures/shell';
import { dashboardRoutes } from './fixtures/dashboard';
import { boardRoutes } from './fixtures/board';

export const routes: MockRoute[] = [
  ...authRoutes,
  ...shellRoutes,
  ...dashboardRoutes,
  ...boardRoutes,
];
