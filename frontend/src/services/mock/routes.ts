import type { MockRoute } from './types';
import { authRoutes } from './fixtures/auth';
import { shellRoutes } from './fixtures/shell';
import { dashboardRoutes } from './fixtures/dashboard';
import { boardRoutes } from './fixtures/board';
import { partMasterRoutes } from './fixtures/partmaster';
import { configurationRoutes } from './fixtures/configuration';
import { changemgmtRoutes } from './fixtures/changemgmt';
import { inventoryRoutes } from './fixtures/inventory';
import { settingsRoutes } from './fixtures/settings';
import { documentsFixtureRoutes } from './fixtures/documents';
import { projectsFixtureRoutes } from './fixtures/projects';

export const routes: MockRoute[] = [
  ...authRoutes,
  ...partMasterRoutes,
  ...configurationRoutes,
  ...shellRoutes,
  ...dashboardRoutes,
  ...boardRoutes,
  ...changemgmtRoutes,
  ...inventoryRoutes,
  ...settingsRoutes,
  ...documentsFixtureRoutes,
  ...projectsFixtureRoutes,
];
