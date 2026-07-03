export function greeting(hour: number): string {
  if (hour >= 5 && hour < 12) return '早上好';
  if (hour >= 12 && hour < 18) return '下午好';
  return '晚上好';
}

export function relativeTime(iso: string, nowMs: number): string {
  if (!iso) return '';
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return '';
  const diff = Math.floor((nowMs - t) / 1000);
  if (diff < 60) return '刚刚';
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
  return `${Math.floor(diff / 86400)}天前`;
}

export type StatusKey = 'draft' | 'frozen' | 'released' | 'obsolete';
export interface Distribution {
  total: number;
  draft: number; frozen: number; released: number; obsolete: number;
  pct: Record<StatusKey, number>;
}

export function statusDistribution(items: { status: string }[]): Distribution {
  const d: Distribution = {
    total: 0, draft: 0, frozen: 0, released: 0, obsolete: 0,
    pct: { draft: 0, frozen: 0, released: 0, obsolete: 0 },
  };
  for (const it of items) {
    d.total++;
    if (it.status === 'draft' || it.status === 'frozen' || it.status === 'released' || it.status === 'obsolete') {
      d[it.status]++;
    }
  }
  if (d.total > 0) {
    (['draft', 'frozen', 'released', 'obsolete'] as StatusKey[]).forEach((k) => {
      d.pct[k] = Math.round((d[k] / d.total) * 100);
    });
  }
  return d;
}

export function overdueDays(plannedEnd: string | null, nowMs: number): number {
  if (!plannedEnd) return 0;
  const t = Date.parse(plannedEnd);
  if (Number.isNaN(t)) return 0;
  const diff = Math.floor((nowMs - t) / 86400000);
  return diff > 0 ? diff : 0;
}
