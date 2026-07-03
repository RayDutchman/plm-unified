import { describe, it, expect } from 'vitest';
import { greeting, relativeTime, statusDistribution, overdueDays, dedupeRecentRefs, flattenFavorites, formatActivity } from './aggregate';

describe('greeting', () => {
  it('按小时返回问候语', () => {
    expect(greeting(8)).toBe('早上好');
    expect(greeting(14)).toBe('下午好');
    expect(greeting(21)).toBe('晚上好');
    expect(greeting(0)).toBe('晚上好');
  });
});

describe('relativeTime', () => {
  const now = Date.parse('2026-07-03T12:00:00Z');
  it('分钟/小时/天', () => {
    expect(relativeTime('2026-07-03T11:58:00Z', now)).toBe('2分钟前');
    expect(relativeTime('2026-07-03T09:00:00Z', now)).toBe('3小时前');
    expect(relativeTime('2026-07-01T12:00:00Z', now)).toBe('2天前');
  });
  it('刚刚 / 空值', () => {
    expect(relativeTime('2026-07-03T11:59:30Z', now)).toBe('刚刚');
    expect(relativeTime('', now)).toBe('');
  });
});

describe('statusDistribution', () => {
  it('计数并给出百分比', () => {
    const items = [
      { status: 'draft' }, { status: 'released' }, { status: 'released' },
      { status: 'frozen' }, { status: 'obsolete' },
    ];
    const d = statusDistribution(items);
    expect(d.total).toBe(5);
    expect(d.released).toBe(2);
    expect(d.pct.released).toBe(40);
    expect(d.pct.draft).toBe(20);
  });
  it('空数组不除零', () => {
    const d = statusDistribution([]);
    expect(d.total).toBe(0);
    expect(d.pct.released).toBe(0);
  });
});

describe('overdueDays', () => {
  const now = Date.parse('2026-07-03T12:00:00Z');
  it('过期返回正天数，未过期返回 0', () => {
    expect(overdueDays('2026-06-30', now)).toBe(3);
    expect(overdueDays('2026-07-10', now)).toBe(0);
    expect(overdueDays(null, now)).toBe(0);
  });
});

describe('dedupeRecentRefs', () => {
  it('按 target 去重保留最新，仅保留实体类型，限量', () => {
    const logs = [
      { target_type: 'part', target_id: 'p1', action: 'update', created_at: '2026-07-03T10:00:00Z' },
      { target_type: 'part', target_id: 'p1', action: 'update', created_at: '2026-07-03T09:00:00Z' },
      { target_type: 'document', target_id: 'd1', action: 'create', created_at: '2026-07-03T08:00:00Z' },
      { target_type: 'user', target_id: 'u1', action: 'update', created_at: '2026-07-03T11:00:00Z' },
    ] as any;
    const refs = dedupeRecentRefs(logs, 5);
    expect(refs.map((r) => r.targetId)).toEqual(['p1', 'd1']);
    expect(refs[0].at).toBe('2026-07-03T10:00:00Z');
  });
});

describe('flattenFavorites', () => {
  it('递归展平文件夹树的 items 并限量', () => {
    const resp = { folders: [
      { items: [{ id: 'i1', entity_type: 'part', entity_id: 'p1', code: 'P-1', name: '零件一' }],
        children: [{ items: [{ id: 'i2', entity_type: 'document', entity_id: 'd1', code: 'D-1', name: '文档一' }], children: [] }] },
    ] };
    const favs = flattenFavorites(resp, 10);
    expect(favs.map((f) => f.code)).toEqual(['P-1', 'D-1']);
  });
});

describe('formatActivity', () => {
  it('组合动作与对象为可读句', () => {
    const log = { username: '张三', action: 'update', target_type: 'part', target_id: 'p1', detail: 'P-0148', created_at: '2026-07-03T11:50:00Z' } as any;
    const a = formatActivity(log, Date.parse('2026-07-03T12:00:00Z'));
    expect(a.text).toBe('张三 更新了零件');
    expect(a.time).toBe('10分钟前');
    expect(a.initial).toBe('张');
  });
});
