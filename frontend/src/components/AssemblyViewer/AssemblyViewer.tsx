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
 *   - 模型原始坐标已在 DocDoku/plm-unified 后端以米为单位存储
 *   - 前端不做额外缩放（场景单位 = 米）
 */

import { useRef, useEffect, useMemo, useState } from 'react';
import * as THREE from 'three';
import { useThree } from '@react-three/fiber';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { Line2 } from 'three/examples/jsm/lines/Line2.js';
import { LineGeometry } from 'three/examples/jsm/lines/LineGeometry.js';
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js';
import { useAssemblyStore, type AssemblyInstance } from '../../stores/assemblyStore';

const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath('/draco/');

const gltfLoader = new GLTFLoader();
gltfLoader.setDRACOLoader(dracoLoader);

/** 边线材质（全局共享） */
const edgeMat = new LineMaterial({ color: 0x222222, linewidth: 0.8, depthTest: true });
/** 选中高亮发光颜色 */
const HIGHLIGHT_EMISSIVE = new THREE.Color(0x224488);

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
    // 需要复制一份，因为 GLTFLoader 会消耗 ArrayBuffer
    const copy = buffer.slice(0);
    gltfLoader.parse(copy, '', (gltf) => {
      const root = gltf.scene;

      // 克隆材质，独立控制高亮
      root.traverse((child) => {
        const m = child as THREE.Mesh;
        if (m.isMesh && m.material && !Array.isArray(m.material)) {
          m.material = (m.material as THREE.Material).clone();
        }
      });

      // 添加 Line2 边线轮廓
      root.traverse((child) => {
        const m = child as THREE.Mesh;
        if (!m.isMesh || m.name === '_edges') return;
        const edges = new THREE.EdgesGeometry(m.geometry, 15);
        const pos = edges.getAttribute('position');
        if (!pos || pos.count === 0) return;
        const positions: number[] = [];
        for (let i = 0; i < pos.count; i++) {
          positions.push(pos.getX(i), pos.getY(i), pos.getZ(i));
        }
        const lineGeo = new LineGeometry();
        lineGeo.setPositions(positions);
        const line = new Line2(lineGeo, edgeMat);
        line.name = '_edges';
        line.computeLineDistances();
        m.add(line);
      });

      setScene(root);
    }, (err) => {
      console.warn('[InstanceMesh] GLB 解析失败:', instance.id, err);
    });
  }, [buffer, instance.id]);

  // 应用实例变换矩阵
  useEffect(() => {
    if (!groupRef.current) return;
    const mat4 = new THREE.Matrix4().fromArray(instance.matrix);
    groupRef.current.matrix.copy(mat4);
    groupRef.current.matrix.decompose(
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
      if (!m.isMesh) return;
      const mat = m.material;
      if (Array.isArray(mat)) return;
      const std = mat as THREE.MeshStandardMaterial;
      if (selected) {
        std.emissive = HIGHLIGHT_EMISSIVE.clone();
        std.emissiveIntensity = 0.5;
      } else {
        std.emissive?.setHex(0x000000);
        std.emissiveIntensity = 0;
      }
      std.needsUpdate = true;
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
  const { gl } = useThree();

  // 更新 LineMaterial 分辨率（必须，否则线宽不正确）
  useEffect(() => {
    edgeMat.resolution.set(gl.domElement.clientWidth, gl.domElement.clientHeight);
  }, [gl]);

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
