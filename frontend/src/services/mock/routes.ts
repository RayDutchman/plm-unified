import type { MockRoute } from './types';
import { authRoutes } from './fixtures/auth';
import { dashboardRoutes } from './fixtures/dashboard';
import { boardRoutes } from './fixtures/board';

export const routes: MockRoute[] = [
  ...authRoutes,
  ...dashboardRoutes,
  ...boardRoutes,
];
