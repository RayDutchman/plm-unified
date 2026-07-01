import api from './api';

export const projectAxios = api;

const base = '/projects';

export const projectApi = {
  listProjects: () => api.get(base),
  getProject: (id: string) => api.get(`${base}/${id}`),
  createProject: (data: any) => api.post(base, data),
  updateProject: (id: string, data: any) => api.put(`${base}/${id}`, data),
  deleteProject: (id: string) => api.delete(`${base}/${id}`),
  listMembers: (id: string) => api.get(`${base}/${id}/members`),
  addMember: (id: string, data: { user_id: string; role_in_project?: string }) =>
    api.post(`${base}/${id}/members`, data),
  removeMember: (id: string, userId: string) => api.delete(`${base}/${id}/members/${userId}`),
  listTasks: (id: string) => api.get(`${base}/${id}/tasks`),
  createTask: (id: string, data: any) => api.post(`${base}/${id}/tasks`, data),
  updateTask: (id: string, taskId: string, data: any) => api.put(`${base}/${id}/tasks/${taskId}`, data),
  updateTaskStatus: (id: string, taskId: string, status: string) =>
    api.patch(`${base}/${id}/tasks/${taskId}/status`, { status }),
  moveTask: (id: string, taskId: string, data: { parent_id?: string | null; sort_order?: number }) =>
    api.post(`${base}/${id}/tasks/${taskId}/move`, data),
  reorderTask: (id: string, data: { task_id: string; new_parent_id?: string | null; new_sort_order: number }) =>
    api.post(`${base}/tasks/reorder`, data),
  deleteTask: (id: string, taskId: string) => api.delete(`${base}/${id}/tasks/${taskId}`),
  listLinks: (id: string, taskId: string) => api.get(`${base}/${id}/tasks/${taskId}/links`),
  addLink: (id: string, taskId: string, data: { entity_type: string; entity_id: string }) =>
    api.post(`${base}/${id}/tasks/${taskId}/links`, data),
  removeLink: (id: string, taskId: string, linkId: string) =>
    api.delete(`${base}/${id}/tasks/${taskId}/links/${linkId}`),
  listComments: (id: string, taskId: string) => api.get(`${base}/${id}/tasks/${taskId}/comments`),
  addComment: (id: string, taskId: string, content: string) =>
    api.post(`${base}/${id}/tasks/${taskId}/comments`, { content }),
  deleteComment: (id: string, taskId: string, commentId: string) =>
    api.delete(`${base}/${id}/tasks/${taskId}/comments/${commentId}`),
  getGantt: (id: string) => api.get(`${base}/${id}/gantt`),
  autoSchedule: (id: string) => api.post(`${base}/${id}/auto-schedule`),
  listDeps: (id: string) => api.get(`${base}/${id}/deps`),
  addDep: (id: string, data: { predecessor_id: string; successor_id: string; dep_type?: string; lag_days?: number }) =>
    api.post(`${base}/${id}/deps`, data),
  removeDep: (id: string, depId: string) => api.delete(`${base}/${id}/deps/${depId}`),
};
