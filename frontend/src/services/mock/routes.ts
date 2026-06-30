import type { MockRoute } from './types';
import { authRoutes } from './fixtures/auth';
import { shellRoutes } from './fixtures/shell';
import { dashboardRoutes } from './fixtures/dashboard';
import { boardRoutes } from './fixtures/board';
import { partMasterRoutes } from './fixtures/partmaster';
import { configurationRoutes } from './fixtures/configuration';

export const routes: MockRoute[] = [
  ...authRoutes,
  ...partMasterRoutes,
  ...configurationRoutes,
  ...shellRoutes,
  ...dashboardRoutes,
  ...boardRoutes,
];
