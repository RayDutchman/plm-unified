/**
 * AssemblyViewer.tsx
 *
 * 装配体查看器核心渲染组件，在 R3F Canvas 内运行。
 *
 * 工作流：
 *   1. 从 assemblyStore 读取 instances 列表（来自 instances API）
 *   2. LODController 根据相机距离调度 GeometryWorker 异步拉取 GLB
 *   3. 每个实例收到 buffer 后，GLTFLoader 解析并用 R3F matrix prop 放置到正确位置
 *   4. 支持点击高亮选中（蓝色包围盒）及边线开关
 *
 * 实例变换约定：
 *   - matrix 是列优先 16 元素数组，Three.js Matrix4.fromArray() 直接兼容
 *   - 后端存储单位为毫米，场景单位同毫米
 */

import { useRef, useEffect, useMemo, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { useAssemblyStore, type AssemblyInstance } from '../../stores/assemblyStore';

const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath('/draco/');

const gltfLoader = new GLTFLoader();
gltfLoader.setDRACOLoader(dracoLoader);

const HIGHLIGHT_EMISSIVE = new THREE.Color(0x224488);
const EDGES_COLOR = 0x222222;
const EDGES_THRESHOLD = 30;

/** 为 mesh 添加或移除边线 */
function manageEdges(mesh: THREE.Mesh, enabled: boolean) {
  // 移除旧边线
  const old = mesh.getObjectByName('_edges');
  if (old) mesh.remove(old);
  if (!enabled) return;

  if (!mesh.geometry) return;
  const edgesGeo = new THREE.EdgesGeometry(mesh.geometry, EDGES_THRESHOLD);
  const segs = new THREE.LineSegments(edgesGeo, new THREE.LineBasicMaterial({ color: EDGES_COLOR }));
  segs.name = '_edges';
  mesh.add(segs);
}

// ---- 单个实例组件 ----

interface InstanceMeshProps {
  instance: AssemblyInstance;
  buffer: ArrayBuffer | null;
  selected: boolean;
  onSelect: (id: string) => void;
}

function InstanceMesh({ instance, buffer, selected, onSelect }: InstanceMeshProps) {
  const [scene, setScene] = useState<THREE.Group | null>(null);
  const showEdges = useAssemblyStore((s) => s.showEdges);
  const pointerDown = useRef<{ x: number; y: number } | null>(null);

  // R3F matrix prop：用 useMemo 缓存，每次 matrix 数组引用变化时重建
  const instanceMatrix = useMemo(
    () => new THREE.Matrix4().fromArray(instance.matrix),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [instance.matrix],
  );

  // 解析 GLB buffer → Three.js scene，克隆材质以独立控制高亮
  useEffect(() => {
    if (!buffer) return;
    const copy = buffer.slice(0);
    gltfLoader.parse(copy, '', (gltf) => {
      const root = gltf.scene;

      root.traverse((child) => {
        const m = child as THREE.Mesh;
        if (!m.isMesh || !m.material) return;
        if (Array.isArray(m.material)) {
          m.material = m.material.map((mat) => mat.clone());
        } else {
          m.material = (m.material as THREE.Material).clone();
        }
      });

      // 初始边线状态
      root.traverse((child) => {
        const m = child as THREE.Mesh;
        if (!m.isMesh || m.name === '_edges') return;
        manageEdges(m, showEdges);
      });

      setScene(root);
    }, (err) => {
      console.warn('[InstanceMesh] GLB 解析失败:', instance.id, err);
    });
  }, [buffer, instance.id, showEdges]);

  // 边线开关更新（scene 已存在时）
  useEffect(() => {
    if (!scene) return;
    scene.traverse((child) => {
      const m = child as THREE.Mesh;
      if (!m.isMesh || m.name === '_edges') return;
      manageEdges(m, showEdges);
    });
  }, [showEdges, scene]);

  // 高亮/取消高亮
  useEffect(() => {
    if (!scene) return;
    scene.traverse((child) => {
      const m = child as THREE.Mesh;
      if (!m.isMesh || !m.material || m.name === '_edges') return;
      const mats = Array.isArray(m.material) ? m.material : [m.material];
      for (const mat of mats) {
        if (!(mat instanceof THREE.MeshStandardMaterial)) continue;
        if (selected) {
          mat.emissive.copy(HIGHLIGHT_EMISSIVE);
          mat.emissiveIntensity = 0.5;
        } else {
          mat.emissive.setHex(0x000000);
          mat.emissiveIntensity = 0;
        }
        mat.needsUpdate = true;
      }
    });
  }, [selected, scene]);

  const handlePointerDown = (e: any) => {
    pointerDown.current = { x: e.clientX, y: e.clientY };
  };

  const handleClick = (e: any) => {
    e.stopPropagation();
    if (pointerDown.current) {
      const dx = e.clientX - pointerDown.current.x;
      const dy = e.clientY - pointerDown.current.y;
      pointerDown.current = null;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) return;
    }
    onSelect(instance.id);
  };

  if (!scene && !instance.geometryFullName) {
    // 无几何数据的实例 → 渲染占位球体
    const bboxCenter = new THREE.Vector3(
      (instance.xMin + instance.xMax) / 2,
      (instance.yMin + instance.yMax) / 2,
      (instance.zMin + instance.zMax) / 2,
    );
    return (
      <group matrix={instanceMatrix} matrixAutoUpdate={false}>
        <mesh position={bboxCenter} onPointerDown={handlePointerDown} onClick={handleClick}>
          <sphereGeometry args={[3, 8, 6]} />
          <meshStandardMaterial color={0x888888} roughness={0.8} metalness={0.1} />
        </mesh>
      </group>
    );
  }

  if (!scene) return null;

  return (
    <group matrix={instanceMatrix} matrixAutoUpdate={false}>
      <primitive
        object={scene}
        onPointerDown={handlePointerDown}
        onClick={handleClick}
      />
    </group>
  );
}

// ---- 选中包围盒高亮 ----

function SelectionBox({ instance }: { instance: AssemblyInstance }) {
  const { geometry, matrix } = useMemo(() => {
    const center = new THREE.Vector3(
      (instance.xMin + instance.xMax) / 2,
      (instance.yMin + instance.yMax) / 2,
      (instance.zMin + instance.zMax) / 2,
    );
    const geo = new THREE.EdgesGeometry(new THREE.BoxGeometry(
      instance.xMax - instance.xMin,
      instance.yMax - instance.yMin,
      instance.zMax - instance.zMin,
    ));
    const mat4 = new THREE.Matrix4().fromArray(instance.matrix);
    mat4.setPosition(center.applyMatrix4(mat4));
    return { geometry: geo, matrix: mat4 };
  }, [instance]);

  return (
    <lineSegments geometry={geometry} matrix={matrix} matrixAutoUpdate={false}>
      <lineBasicMaterial color={0x4488ff} />
    </lineSegments>
  );
}

// ---- 主组件 ----

export function AssemblyViewer() {
  const instances = useAssemblyStore((s) => s.instances);
  const bufferCache = useAssemblyStore((s) => s.bufferCache);
  const selectedId = useAssemblyStore((s) => s.selectedId);
  const selectInstance = useAssemblyStore((s) => s.selectInstance);

  return (
    <group>
      {instances.map((inst) => {
        const buffer = inst.loadedUrl ? (bufferCache.get(inst.loadedUrl) ?? null) : null;
        return (
          <InstanceMesh
            key={inst.id}
            instance={inst}
            buffer={buffer}
            selected={selectedId === inst.id}
            onSelect={selectInstance}
          />
        );
      })}
      {selectedId && (() => {
        const inst = instances.find((i) => i.id === selectedId);
        return inst ? <SelectionBox instance={inst} /> : null;
      })()}
    </group>
  );
}
