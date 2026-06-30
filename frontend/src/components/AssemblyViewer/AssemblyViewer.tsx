/**
 * AssemblyViewer.tsx
 *
 * 装配体查看器核心渲染组件，在 R3F Canvas 内运行。
 *
 * 工作流：
 *   1. 从 assemblyStore 读取 instances 列表（来自 instances API）
 *   2. LODController 根据相机距离调度 GeometryWorker 异步拉取 GLB
 *   3. 每个实例收到 buffer 后，GLTFLoader 解析并 applyMatrix4 放置到正确位置
 *   4. 支持点击高亮选中（蓝色包围盒）
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

/** 选中高亮发光颜色 */
const HIGHLIGHT_EMISSIVE = new THREE.Color(0x224488);

/**
 * 修正材质发白问题：
 * GLB 里的 MeshStandardMaterial 默认 roughness=1，在 IBL 下整体偏白。
 * 调整为 roughness=0.6、metalness=0.15，保留原始颜色，视觉效果更立体。
 */
function tuneMaterial(mat: THREE.Material) {
  if (!(mat instanceof THREE.MeshStandardMaterial)) return;
  // 只在 roughness 接近默认值（1.0）时才调整，避免覆盖 GLB 里已有的 PBR 设置
  if (mat.roughness > 0.85) mat.roughness = 0.6;
  if (mat.metalness < 0.05) mat.metalness = 0.15;
  mat.needsUpdate = true;
}

// ---- 单个实例组件 ----

interface InstanceMeshProps {
  instance: AssemblyInstance;
  buffer: ArrayBuffer | null;
  selected: boolean;
  onSelect: (id: string) => void;
}

function InstanceMesh({ instance, buffer, selected, onSelect }: InstanceMeshProps) {
  const groupRef = useRef<THREE.Group>(null);
  const [scene, setScene] = useState<THREE.Group | null>(null);
  const pointerDown = useRef<{ x: number; y: number } | null>(null);

  // 解析 GLB buffer → Three.js scene
  useEffect(() => {
    if (!buffer) return;
    const copy = buffer.slice(0);
    gltfLoader.parse(copy, '', (gltf) => {
      const root = gltf.scene;

      // 克隆材质（独立控制高亮），并调整 PBR 参数
      root.traverse((child) => {
        const m = child as THREE.Mesh;
        if (!m.isMesh || !m.material) return;
        if (Array.isArray(m.material)) {
          m.material = m.material.map((mat) => {
            const c = mat.clone();
            tuneMaterial(c);
            return c;
          });
        } else {
          m.material = (m.material as THREE.Material).clone();
          tuneMaterial(m.material);
        }
      });

      setScene(root);
    }, (err) => {
      console.warn('[InstanceMesh] GLB 解析失败:', instance.id, err);
    });
  }, [buffer, instance.id]);

  // 应用实例变换矩阵（列优先，Matrix4.fromArray 直接兼容）
  useEffect(() => {
    if (!groupRef.current) return;
    const mat4 = new THREE.Matrix4().fromArray(instance.matrix);
    mat4.decompose(
      groupRef.current.position,
      groupRef.current.quaternion,
      groupRef.current.scale,
    );
  }, [instance.matrix]);

  // 高亮/取消高亮
  useEffect(() => {
    if (!scene) return;
    scene.traverse((child) => {
      const m = child as THREE.Mesh;
      if (!m.isMesh || !m.material) return;
      const mats = Array.isArray(m.material) ? m.material : [m.material];
      for (const mat of mats) {
        const std = mat as THREE.MeshStandardMaterial;
        if (!std.emissive) continue;
        if (selected) {
          std.emissive.copy(HIGHLIGHT_EMISSIVE);
          std.emissiveIntensity = 0.5;
        } else {
          std.emissive.setHex(0x000000);
          std.emissiveIntensity = 0;
        }
        std.needsUpdate = true;
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

  if (!scene) return null;

  return (
    <group ref={groupRef}>
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
  const ref = useRef<THREE.LineSegments>(null);

  const { geometry, matrix } = useMemo(() => {
    const box = new THREE.Box3(
      new THREE.Vector3(instance.xMin, instance.yMin, instance.zMin),
      new THREE.Vector3(instance.xMax, instance.yMax, instance.zMax),
    );
    const geo = new THREE.EdgesGeometry(new THREE.BoxGeometry(
      instance.xMax - instance.xMin,
      instance.yMax - instance.yMin,
      instance.zMax - instance.zMin,
    ));
    const center = box.getCenter(new THREE.Vector3());
    const mat4 = new THREE.Matrix4().fromArray(instance.matrix);
    const worldCenter = center.applyMatrix4(mat4);
    const m = new THREE.Matrix4().fromArray(instance.matrix);
    m.setPosition(worldCenter);
    return { geometry: geo, matrix: m };
  }, [instance]);

  return (
    <lineSegments ref={ref} geometry={geometry} matrix={matrix} matrixAutoUpdate={false}>
      <lineBasicMaterial color={0x4488ff} linewidth={2} />
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
        // 找该实例已加载的 buffer
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
