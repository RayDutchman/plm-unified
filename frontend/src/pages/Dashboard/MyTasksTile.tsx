import { useEffect, useState, useMemo } from 'react';
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
  const groups = useMemo(() => {
    const map = new Map<string, { project: { id: string; code: string; name: string }; tasks: MyTaskItem[] }>();
    for (const t of items) {
      if (!map.has(t.project_id)) {
        map.set(t.project_id, { project: { id: t.project_id, code: t.project_code, name: t.project_name }, tasks: [] });
      }
      map.get(t.project_id)!.tasks.push(t);
    }
    return Array.from(map.values());
  }, [items]);

  const overdueTotal = items.filter((t) => overdueDays(t.planned_end, now) > 0).length;

  return (
    <Tile
      title="我的任务"
      icon={<span>✅</span>}
      right={overdueTotal > 0 ? <span className="text-xs text-red-500">{overdueTotal} 逾期</span> : undefined}
      className="min-h-[220px]"
    >
      {loaded && items.length === 0 ? <EmptyState text="暂无指派给你的任务" /> : (
        <div className="flex flex-col gap-3 overflow-y-auto max-h-[360px] pr-1">
          {groups.map((g) => (
            <Link
              key={g.project.id}
              to={`/projects?project_id=${g.project.id}`}
              className="block rounded-lg border border-gray-100 bg-gray-50 hover:shadow-sm transition-shadow"
            >
              <div className="px-3 py-2 border-b border-gray-200 text-xs font-medium text-gray-500">
                {g.project.code} · {g.project.name}
                <span className="text-gray-400 ml-2">({g.tasks.length})</span>
              </div>
              {g.tasks.map((t) => {
                const od = overdueDays(t.planned_end, now);
                const startStr = fmtDate(t.planned_start);
                const endStr = fmtDate(t.planned_end);
                const dateRange = startStr || endStr ? `${startStr || '...'} ~ ${endStr || '...'}` : null;
                return (
                  <div key={t.task_id} className={`px-3 py-2 flex items-center gap-2 ${od > 0 ? 'bg-red-50/50' : ''}`}>
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${od > 0 ? 'bg-red-500' : 'bg-gray-400'}`} />
                    <span className="text-sm text-gray-800 truncate flex-1">{t.name}</span>
                    <span className={`text-xs px-1 rounded shrink-0 ${STATUS_CLS[t.status] || 'bg-gray-100 text-gray-600'}`}>{t.status}</span>
                    {dateRange && (
                      <span className={`text-xs shrink-0 ${od > 0 ? 'text-red-500' : 'text-gray-400'}`}>
                        {dateRange}
                      </span>
                    )}
                  </div>
                );
              })}
            </Link>
          ))}
        </div>
      )}
    </Tile>
  );
}
