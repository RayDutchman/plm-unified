import type { OperationLog } from '../types';
import { formatDateTime } from '../utils/date';

interface OperationLogTableProps {
  logs: OperationLog[];
  loading?: boolean;
}

const ACTION_CLASS: Record<string, string> = {
  '创建图文档': 'bg-green-100 text-green-800',
  '创建任务': 'bg-green-100 text-green-800',
  '删除任务': 'bg-red-100 text-red-800',
  '软删除图文档': 'bg-red-100 text-red-800',
  '任务状态变更': 'bg-blue-100 text-blue-800',
  '更新图文档': 'bg-gray-100 text-gray-700',
  '图文档升版': 'bg-purple-100 text-purple-800',
  '上传附件': 'bg-blue-50 text-blue-700',
  '删除附件': 'bg-orange-50 text-orange-700',
};

interface ColumnConfig {
  key: string;
  label: string;
  width?: number;
}

// 表头与列宽配置，避免 thead/tbody 重复定义 colgroup
const COLUMNS: ColumnConfig[] = [
  { key: 'created_at', label: '时间', width: 150 },
  { key: 'username', label: '用户', width: 80 },
  { key: 'action', label: '操作', width: 96 },
  { key: 'detail', label: '详情' },
];

export default function OperationLogTable({ logs, loading }: OperationLogTableProps) {
  if (loading) return <div className="text-center text-gray-400 py-8">加载中...</div>;
  if (logs.length === 0) return <div className="text-center text-gray-400 py-8">暂无操作记录</div>;

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <div className="max-h-64 overflow-y-auto">
        <table className="w-full text-sm table-fixed">
          <colgroup>
            {COLUMNS.map((col) => (
              <col key={col.key} style={col.width ? { width: `${col.width}px` } : undefined} />
            ))}
          </colgroup>
          <thead className="bg-gray-50 border-b border-gray-200 sticky top-0 z-10">
            <tr>
              {COLUMNS.map((col) => (
                <th key={col.key} className="text-left px-3 py-2 text-xs font-medium text-gray-500">
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {logs.map((l) => (
              <tr key={l.id}>
                <td className="px-3 py-2 text-gray-500 whitespace-nowrap align-top">{formatDateTime(l.created_at)}</td>
                <td className="px-3 py-2 align-top truncate">{l.username}</td>
                <td className="px-3 py-2 align-top">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${ACTION_CLASS[l.action] ?? 'bg-gray-100 text-gray-700'}`}>
                    {l.action}
                  </span>
                </td>
                <td className="px-3 py-2 text-gray-500 break-words align-top">{l.detail || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
