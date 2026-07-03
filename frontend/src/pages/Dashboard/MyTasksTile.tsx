import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Tile, EmptyState } from './tiles';
import { projectApi } from '../../services/projectApi';
import { overdueDays } from './lib/aggregate';
import type { MyTaskItem } from '../../types';

const STATUS_CLS: Record<string, string> = {
  '未开始': 'bg-gray-100 text-gray-600',
  '进行中': 'bg-blue-50 text-blue-700',
  '挂起': 'bg-amber-50 text-amber-700',
};
const PRIO_DOT: Record<string, string> = { '高': '#E24B4A', '中': '#EF9F27', '低': '#888780' };
const TYPE_LABEL: Record<string, string> = { '任务': '📋', '里程碑': '🏁', '评审': '🔍' };

function fmtDate(d: string | null): string {
  if (!d) return '';
  return d.slice(0, 10);
}

export function MyTasksTile({ onOverdue }: { onOverdue?: (n: number) => void }) {
  const [items, setItems] = useState<MyTaskItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let cancelled = false;
    projectApi.myTasks()
      .then((res) => {
        if (cancelled) return;
        const list: MyTaskItem[] = res.data?.items ?? [];
        setItems(list);
        const now = Date.now();
        onOverdue?.(list.filter((t) => overdueDays(t.planned_end, now) > 0).length);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoaded(true); });
    return () => { cancelled = true; };
  }, [onOverdue]);

  const now = Date.now();
  const overdueTotal = items.filter((t) => overdueDays(t.planned_end, now) > 0).length;
  return (
    <Tile
      title="我的任务"
      icon={<span>✅</span>}
      right={overdueTotal > 0 ? <span className="text-xs text-red-500">{overdueTotal} 逾期</span> : undefined}
      className="min-h-[220px]"
    >
      {loaded && items.length === 0 ? <EmptyState text="暂无指派给你的任务" /> : (
        <div className="flex flex-col gap-3">
          {items.slice(0, 4).map((t) => {
            const od = overdueDays(t.planned_end, now);
            const startStr = fmtDate(t.planned_start);
            const endStr = fmtDate(t.planned_end);
            const dateRange = startStr || endStr ? `${startStr || '...'} ~ ${endStr || '...'}` : null;
            return (
              <Link
                key={t.task_id}
                to={`/projects?project_id=${t.project_id}&task_id=${t.task_id}`}
                className={`block rounded-lg border p-3 hover:shadow-sm transition-shadow ${od > 0 ? 'border-red-200 bg-red-50/50' : 'border-gray-100 bg-gray-50'}`}
              >
                <div className="text-xs text-gray-400 mb-1">{t.project_code} · {t.project_name}</div>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <span className="text-sm font-medium text-gray-800 truncate">{t.name}</span>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-gray-500">{t.code}</span>
                  {t.task_type && (
                    <span className="text-xs text-gray-500">
                      {TYPE_LABEL[t.task_type] || ''} {t.task_type}
                    </span>
                  )}
                  <span className={`text-xs px-1.5 rounded ${STATUS_CLS[t.status] || 'bg-gray-100 text-gray-600'}`}>
                    {t.status}
                  </span>
                  <span className="flex items-center gap-0.5 text-xs text-gray-500">
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: PRIO_DOT[t.priority] || '#888' }} />
                    {t.priority}
                  </span>
                  {dateRange && (
                    <span className={`text-xs ${od > 0 ? 'text-red-500 font-medium' : 'text-gray-400'}`}>
                      {dateRange}
                      {od > 0 && <span className="ml-1">· 逾期{od}天</span>}
                    </span>
                  )}
                </div>
                {t.description && (
                  <div className="text-xs text-gray-400 mt-1 truncate">{t.description}</div>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </Tile>
  );
}
