/**
 * GeometryWorker.ts
 *
 * Web Worker，负责按优先级异步拉取 GLB 文件，
 * 避免主线程因网络请求卡顿。
 *
 * 消息协议（主线程 → Worker）：
 *   { type: 'enqueue', jobs: GeometryJob[] }   — 加入待加载队列（去重）
 *   { type: 'cancel', urls: string[] }          — 取消尚未开始的任务
 *   { type: 'clear' }                           — 清空全部队列与缓存
 *   { type: 'setToken', token: string }          — 设置 JWT token（用于 Authorization 头）
 *
 * 消息协议（Worker → 主线程）：
 *   { type: 'loaded', url: string, buffer: ArrayBuffer }   — 加载成功，transferable
 *   { type: 'error',  url: string, message: string }       — 加载失败
 *   { type: 'progress', url: string, percent: number }     — 加载进度（0-100）
 */

export interface GeometryJob {
  /** geometry endpoint URL，如 /api/parts/.../geometry?quality=0&... */
  url: string;
  /** 优先级，数字越大越先加载（默认 0） */
  priority?: number;
}

interface QueueItem extends Required<GeometryJob> {
  cancelled: boolean;
}

let jwtToken = '';
const queue: QueueItem[] = [];
/** 已加载成功的 URL 集合，防止重复请求 */
const loaded = new Set<string>();
/** 当前正在进行的并发数 */
let inflight = 0;
const MAX_CONCURRENCY = 3;

// ---- 队列调度 ----

function enqueue(jobs: GeometryJob[]) {
  for (const job of jobs) {
    if (loaded.has(job.url)) continue;
    const existing = queue.find((q) => q.url === job.url);
    if (existing) {
      // 更新优先级（取更高值）
      existing.priority = Math.max(existing.priority, job.priority ?? 0);
      existing.cancelled = false;
      continue;
    }
    queue.push({ url: job.url, priority: job.priority ?? 0, cancelled: false });
  }
  // 按优先级降序排列
  queue.sort((a, b) => b.priority - a.priority);
  drain();
}

function cancel(urls: string[]) {
  const set = new Set(urls);
  for (const item of queue) {
    if (set.has(item.url)) item.cancelled = true;
  }
}

function clear() {
  queue.length = 0;
  loaded.clear();
}

function drain() {
  while (inflight < MAX_CONCURRENCY) {
    // 找第一个未取消的任务
    const idx = queue.findIndex((q) => !q.cancelled);
    if (idx === -1) break;
    const [item] = queue.splice(idx, 1);
    inflight++;
    fetchGlb(item).finally(() => {
      inflight--;
      drain();
    });
  }
}

async function fetchGlb(item: QueueItem) {
  if (item.cancelled) return;

  const headers: Record<string, string> = {};
  if (jwtToken) headers['Authorization'] = `Bearer ${jwtToken}`;

  try {
    const resp = await fetch(item.url, { headers });
    if (!resp.ok) {
      self.postMessage({ type: 'error', url: item.url, message: `HTTP ${resp.status}` });
      return;
    }

    const reader = resp.body?.getReader();
    const contentLength = Number(resp.headers.get('Content-Length') ?? 0);
    if (!reader) {
      const buffer = await resp.arrayBuffer();
      loaded.add(item.url);
      self.postMessage({ type: 'loaded', url: item.url, buffer }, { transfer: [buffer] });
      return;
    }

    // 流式读取，支持进度上报
    const chunks: Uint8Array[] = [];
    let received = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
      received += value.byteLength;
      if (contentLength > 0) {
        const percent = Math.round((received / contentLength) * 100);
        self.postMessage({ type: 'progress', url: item.url, percent });
      }
    }

    // 合并 chunks
    const total = chunks.reduce((s, c) => s + c.byteLength, 0);
    const merged = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      merged.set(chunk, offset);
      offset += chunk.byteLength;
    }

    loaded.add(item.url);
    self.postMessage(
      { type: 'loaded', url: item.url, buffer: merged.buffer },
      { transfer: [merged.buffer] },
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    self.postMessage({ type: 'error', url: item.url, message: msg });
  }
}

// ---- 消息入口 ----

self.onmessage = (e: MessageEvent) => {
  const { type } = e.data;
  switch (type) {
    case 'enqueue':
      enqueue(e.data.jobs as GeometryJob[]);
      break;
    case 'cancel':
      cancel(e.data.urls as string[]);
      break;
    case 'clear':
      clear();
      break;
    case 'setToken':
      jwtToken = e.data.token as string;
      break;
  }
};
