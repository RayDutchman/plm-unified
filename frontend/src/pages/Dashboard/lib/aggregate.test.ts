import { describe, it, expect } from 'vitest';
import { greeting, relativeTime } from './aggregate';

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
