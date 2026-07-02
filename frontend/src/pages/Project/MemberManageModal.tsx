import { useEffect, useState } from 'react';
import { Modal } from '../../components/Modal';
import { projectApi } from '../../services/projectApi';
import { usersApi } from '../../services/api';
import type { ProjectMember } from '../../types/project';

interface Props {
  open: boolean;
  projectId: string;
  ownerId: string;
  onClose: () => void;
}

const ROLES = ['经理', '成员'];

export default function MemberManageModal({ open, projectId, ownerId, onClose }: Props) {
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [users, setUsers] = useState<{ id: string; real_name: string; username: string }[]>([]);
  const [pickUser, setPickUser] = useState('');
  const [pickRole, setPickRole] = useState('成员');

  const load = async () => {
    const res = await projectApi.listMembers(projectId);
    setMembers(res.data.items);
  };

  useEffect(() => {
    if (!open) return;
    load();
    usersApi.list().then((r) => setUsers(r.data.items || r.data)).catch(() => setUsers([]));
  }, [open, projectId]);

  const handleAdd = async () => {
    if (!pickUser) return;
    try {
      await projectApi.addMember(projectId, { user_id: pickUser, role_in_project: pickRole });
      setPickUser('');
      setPickRole('成员');
      load();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '添加成员失败');
    }
  };

  const handleRemove = async (userId: string) => {
    try {
      await projectApi.removeMember(projectId, userId);
      load();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '移除成员失败');
    }
  };

  const handleRoleChange = async (userId: string, role: string) => {
    try {
      await projectApi.setMemberRole(projectId, userId, role);
      load();
    } catch (err: any) {
      alert(err?.response?.data?.detail || '调整角色失败');
    }
  };

  const memberIds = new Set(members.map((m) => m.user_id));

  return (
    <Modal open={open} title="项目成员管理" onClose={onClose} width="lg">
      <div className="flex gap-2 mb-4">
        <select value={pickUser} onChange={(e) => setPickUser(e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg">
          <option value="">选择用户加入…</option>
          {users.filter((u) => !memberIds.has(u.id)).map((u) => (
            <option key={u.id} value={u.id}>{u.real_name}（{u.username}）</option>
          ))}
        </select>
        <select value={pickRole} onChange={(e) => setPickRole(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg">
          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <button onClick={handleAdd} className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700">添加</button>
      </div>
      <div className="divide-y">
        {members.map((m) => {
          const isOwner = m.user_id === ownerId;
          return (
            <div key={m.id} className="flex items-center gap-2 py-2">
              <span className="font-medium">{m.user_name}</span>
              {isOwner ? (
                // owner 恒为项目负责人(经理),角色不可改
                <span className="text-xs px-2 py-0.5 rounded bg-primary-50 text-primary-700">负责人</span>
              ) : (
                <select value={m.role_in_project} onChange={(e) => handleRoleChange(m.user_id, e.target.value)}
                        className="text-xs border border-gray-300 rounded px-1.5 py-0.5 text-gray-600">
                  {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              )}
              <div className="flex-1" />
              {!isOwner && (
                <button onClick={() => handleRemove(m.user_id)} className="text-red-600 text-sm hover:underline">移除</button>
              )}
            </div>
          );
        })}
      </div>
    </Modal>
  );
}
