import { useEffect, useState } from 'react';
import { usersApi, logsApi, boardApi } from '../../services/api';
import { useDataStore } from '../../stores/data';
import type { User } from '../../types';
import { dedupeRecentRefs, flattenFavorites, formatActivity, type Activity, type FavItem } from './lib/aggregate';

export type { Activity, FavItem } from './lib/aggregate';

export function useUserList(): User[] {
  const [users, setUsers] = useState<User[]>([]);
  useEffect(() => {
    let cancelled = false;
    usersApi.list({ page_size: 10000 })
      .then((res) => {
        if (!cancelled) {
          const d = res.data;
          setUsers(Array.isArray(d) ? d : (d?.items ?? []));
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);
  return users;
}

export interface RecentDisplay { key: string; entityType: string; entityId: string; code: string; name: string; }

export function useRecentEdited(userId: string | undefined, limit = 5): RecentDisplay[] {
  const parts = useDataStore((s) => s.parts);
  const assemblies = useDataStore((s) => s.assemblies);
  const documents = useDataStore((s) => s.documents);
  const configItems = useDataStore((s) => s.configItems);
  const [refs, setRefs] = useState<{ targetType: string; targetId: string }[]>([]);
  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    logsApi.list({ user_id: userId, limit: 60 })
      .then((res) => {
        const logs = res.data?.items ?? res.data ?? [];
        if (!cancelled) setRefs(dedupeRecentRefs(logs, limit));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [userId, limit]);
  const byId = new Map<string, { code: string; name: string }>();
  parts.forEach((p) => byId.set(`part:${p.id}`, { code: (p as any).number ?? '', name: p.name }));
  assemblies.forEach((a) => byId.set(`assembly:${a.id}`, { code: (a as any).number ?? '', name: a.name }));
  documents.forEach((d) => byId.set(`document:${d.id}`, { code: (d as any).code ?? '', name: d.name }));
  configItems.forEach((c) => byId.set(`configuration:${c.id}`, { code: c.code, name: c.name }));
  return refs
    .map((r) => {
      const hit = byId.get(`${r.targetType}:${r.targetId}`);
      return hit ? { key: `${r.targetType}:${r.targetId}`, entityType: r.targetType, entityId: r.targetId, code: hit.code, name: hit.name } : null;
    })
    .filter((x): x is RecentDisplay => x !== null);
}

export function useFavorites(limit = 6): FavItem[] {
  const [favs, setFavs] = useState<FavItem[]>([]);
  useEffect(() => {
    let cancelled = false;
    boardApi.getDashboard()
      .then((res) => {
        if (!cancelled) setFavs(flattenFavorites(res.data, limit));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [limit]);
  return favs;
}

export function useActivityFeed(limit = 6): Activity[] {
  const [acts, setActs] = useState<Activity[]>([]);
  useEffect(() => {
    let cancelled = false;
    logsApi.list({ limit })
      .then((res) => {
        const logs = res.data?.items ?? res.data ?? [];
        const now = Date.now();
        if (!cancelled) setActs(logs.map((l: any) => formatActivity(l, now)));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [limit]);
  return acts;
}
