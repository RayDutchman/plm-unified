import axios from 'axios';
import { useAuthStore } from '../stores/auth';

export const projectAxios = axios.create({ baseURL: '/api/projects', timeout: 30000 });
projectAxios.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const projectApi = {
  listProjects: () => projectAxios.get('/'),
  getProject: (id: string) => projectAxios.get(`/${id}`),
  createProject: (data: any) => projectAxios.post('/', data),
  updateProject: (id: string, data: any) => projectAxios.put(`/${id}`, data),
  deleteProject: (id: string) => projectAxios.delete(`/${id}`),
  listMembers: (id: string) => projectAxios.get(`/${id}/members`),
  addMember: (id: string, data: { user_id: string; role_in_project?: string }) =>
    projectAxios.post(`/${id}/members`, data),
  removeMember: (id: string, userId: string) => projectAxios.delete(`/${id}/members/${userId}`),
  listTasks: (id: string) => projectAxios.get(`/${id}/tasks`),
  createTask: (id: string, data: any) => projectAxios.post(`/${id}/tasks`, data),
  updateTask: (id: string, taskId: string, data: any) => projectAxios.put(`/${id}/tasks/${taskId}`, data),
  updateTaskStatus: (id: string, taskId: string, status: string) =>
    projectAxios.patch(`/${id}/tasks/${taskId}/status`, { status }),
  moveTask: (id: string, taskId: string, data: { parent_id?: string | null; sort_order?: number }) =>
    projectAxios.post(`/${id}/tasks/${taskId}/move`, data),
  reorderTask: (id: string, data: { task_id: string; new_parent_id?: string | null; new_sort_order: number }) =>
    projectAxios.post(`/${id}/tasks/reorder`, data),
  deleteTask: (id: string, taskId: string) => projectAxios.delete(`/${id}/tasks/${taskId}`),
  listLinks: (id: string, taskId: string) => projectAxios.get(`/${id}/tasks/${taskId}/links`),
  addLink: (id: string, taskId: string, data: { entity_type: string; entity_id: string }) =>
    projectAxios.post(`/${id}/tasks/${taskId}/links`, data),
  removeLink: (id: string, taskId: string, linkId: string) =>
    projectAxios.delete(`/${id}/tasks/${taskId}/links/${linkId}`),
  listComments: (id: string, taskId: string) => projectAxios.get(`/${id}/tasks/${taskId}/comments`),
  addComment: (id: string, taskId: string, content: string) =>
    projectAxios.post(`/${id}/tasks/${taskId}/comments`, { content }),
  deleteComment: (id: string, taskId: string, commentId: string) =>
    projectAxios.delete(`/${id}/tasks/${taskId}/comments/${commentId}`),
  getGantt: (id: string) => projectAxios.get(`/${id}/gantt`),
  autoSchedule: (id: string) => projectAxios.post(`/${id}/auto-schedule`),
  listDeps: (id: string) => projectAxios.get(`/${id}/deps`),
  addDep: (id: string, data: { predecessor_id: string; successor_id: string; dep_type?: string; lag_days?: number }) =>
    projectAxios.post(`/${id}/deps`, data),
  removeDep: (id: string, depId: string) => projectAxios.delete(`/${id}/deps/${depId}`),
};
