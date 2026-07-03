import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Tile, EmptyState } from './tiles';
import { projectApi } from '../../services/projectApi';
import { overdueDays } from './lib/aggregate';
import type { MyTaskItem } from '../../types';

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
    <Tile title="我的任务" icon={<span>✅</span>} right={overdueTotal > 0 ? <span className="text-xs text-red-500">{overdueTotal} 逾期</span> : undefined}>
      {loaded && items.length === 0 ? <EmptyState text="暂无指派给你的任务" /> : (
        <div className="flex flex-col gap-2">
          {items.slice(0, 4).map((t) => {
            const od = overdueDays(t.planned_end, now);
            return (
              <Link key={t.task_id} to={`/projects?project_id=${t.project_id}&task_id=${t.task_id}`} className="flex items-center gap-2 text-sm hover:bg-gray-50 rounded px-1">
                <span className="w-3.5 h-3.5 border border-gray-300 rounded-sm shrink-0" />
                <span className="truncate flex-1 text-gray-700">{t.name}</span>
                <span className={`text-xs shrink-0 ${od > 0 ? 'text-red-500' : 'text-gray-400'}`}>
                  {od > 0 ? `逾期 ${od}天` : (t.planned_end || '')}
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </Tile>
  );
}
