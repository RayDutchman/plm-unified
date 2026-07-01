/**
 * LODController.tsx
 *
 * 根据相机与实例的距离，动态决定每个实例应加载的 LOD 质量等级，
 * 并通过 GeometryWorker 优先级队列异步拉取 GLB。
 *
 * LOD 策略（距离指实例包围球中心到相机的距离，scale 归一化后）：
 *   distance < nearThreshold  → quality=0（最高精度）
 *   distance < farThreshold   → quality=1（中等精度）
 *   distance >= farThreshold  → quality=2（低精度）
 *
 * 使用方式：在 AssemblyCanvas 内渲染，会自动读取 assemblyStore 中的实例列表，
 * 并将 GLB buffer 回写给 assemblyStore.setInstanceBuffer()。
 */

import { useEffect, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { GeometryJob } from '../../workers/GeometryWorker';
import { useAssemblyStore } from '../../stores/assemblyStore';
import { useAuthStore } from '../../stores/auth';

/** 两个距离阈值（场景单位） */
const NEAR_THRESHOLD = 8;
const FAR_THRESHOLD = 20;

/** 每帧检查周期（秒），避免每帧都重新计算 */
const CHECK_INTERVAL = 0.5;

export function LODController() {
  const { camera } = useThree();
  const workerRef = useRef<Worker | null>(null);
  const lastCheck = useRef(0);
  const token = useAuthStore((s) => s.token);
  const instances = useAssemblyStore((s) => s.instances);
  const workspaceId = useAssemblyStore((s) => s.workspaceId);
  const setInstanceBuffer = useAssemblyStore((s) => s.setInstanceBuffer);
  const setInstanceError = useAssemblyStore((s) => s.setInstanceError);

  // 初始化 Worker
  useEffect(() => {
    const worker = new Worker(
      new URL('../../workers/GeometryWorker.ts', import.meta.url),
      { type: 'module' },
    );

    worker.onmessage = (e: MessageEvent) => {
      const { type, url, buffer, message } = e.data;
      if (type === 'loaded') {
        setInstanceBuffer(url, buffer as ArrayBuffer);
      } else if (type === 'error') {
        console.warn('[LODController] 加载失败:', url, message);
        setInstanceError(url, message as string);
      }
    };

    workerRef.current = worker;
    return () => {
      worker.postMessage({ type: 'clear' });
      worker.terminate();
      workerRef.current = null;
    };
  }, [setInstanceBuffer, setInstanceError]);

  // token 变化时更新 Worker 内的 JWT
  useEffect(() => {
    if (workerRef.current && token) {
      workerRef.current.postMessage({ type: 'setToken', token });
    }
  }, [token]);

  // 按周期检查，根据相机距离调度加载任务
  useFrame((_, delta) => {
    lastCheck.current += delta;
    if (lastCheck.current < CHECK_INTERVAL) return;
    lastCheck.current = 0;

    const worker = workerRef.current;
    if (!worker || instances.length === 0) return;

    const camPos = camera.position;
    const jobs: GeometryJob[] = [];

    for (const inst of instances) {
      if (!inst.geometryFullName) continue;

      // 计算包围球中心（bbox 中点），应用实例矩阵变换
      const cx = (inst.xMin + inst.xMax) / 2;
      const cy = (inst.yMin + inst.yMax) / 2;
      const cz = (inst.zMin + inst.zMax) / 2;
      const mat4 = new THREE.Matrix4().fromArray(inst.matrix);
      const worldCenter = new THREE.Vector3(cx, cy, cz).applyMatrix4(mat4);
      const dist = camPos.distanceTo(worldCenter);

      // 决定 LOD 等级
      let quality = 2;
      if (dist < NEAR_THRESHOLD) quality = 0;
      else if (dist < FAR_THRESHOLD) quality = 1;

      const url = buildGeometryUrl(inst, quality, workspaceId);
      if (!url) continue;

      // 已加载该 URL 则跳过
      if (inst.loadedUrl === url) continue;

      // 优先级：距离越近越高
      const priority = Math.max(0, Math.round(100 - dist * 4));
      jobs.push({ url, priority });
    }

    if (jobs.length > 0) {
      worker.postMessage({ type: 'enqueue', jobs });
    }
  });

  return null;
}

/**
 * 构建 geometry endpoint URL。
 * /api/parts/{number}/{version}/iterations/{iteration}/geometry?quality={q}&workspace_id={ws}
 */
function buildGeometryUrl(
  inst: {
    partNumber: string;
    version: string;
    iteration: number;
    geometryFullName?: string | null;
  },
  quality: number,
  workspaceId: string,
): string | null {
  if (!inst.geometryFullName) return null;
  const { partNumber, version, iteration } = inst;
  return (
    `/api/parts/${encodeURIComponent(partNumber)}` +
    `/${encodeURIComponent(version)}` +
    `/iterations/${iteration}` +
    `/geometry?quality=${quality}&workspace_id=${encodeURIComponent(workspaceId)}`
  );
}
