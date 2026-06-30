/**
 * AssemblyCanvas.tsx
 *
 * 装配体查看器的 R3F Canvas 容器。
 * 组合：LocalEnvironment + 光照 + CameraController + LODController + AssemblyViewer
 *
 * 与 STPViewer 的 ViewerCanvas 并列，专门用于装配体实例矩阵渲染模式。
 */

import { Suspense, useEffect } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { ArcballControls } from '@react-three/drei';
import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { AssemblyViewer } from './AssemblyViewer';
import { LODController } from './LODController';
import { useAssemblyStore } from '../../stores/assemblyStore';

/** 程序化 IBL 环境光（同 STPViewer，本地生成不依赖外网） */
function LocalEnvironment() {
  const { gl, scene } = useThree();
  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const envMap = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = envMap;
    scene.environmentIntensity = 1.0;
    scene.background = new THREE.Color('#2a2a2e');
    return () => {
      scene.environment = null;
      scene.background = null;
      envMap.dispose();
      pmrem.dispose();
    };
  }, [gl, scene]);
  return null;
}

/** 相机控制器（ArcballControls，Escape 取消选中） */
function CameraSetup() {
  const selectInstance = useAssemblyStore((s) => s.selectInstance);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') selectInstance(null);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectInstance]);

  return <ArcballControls makeDefault />;
}

/** 自动将相机对准所有实例的全局包围盒 */
function AutoFit() {
  const { camera } = useThree();
  const instances = useAssemblyStore((s) => s.instances);

  useEffect(() => {
    if (instances.length === 0) return;
    const box = new THREE.Box3();
    for (const inst of instances) {
      const mat4 = new THREE.Matrix4().fromArray(inst.matrix);
      const localBox = new THREE.Box3(
        new THREE.Vector3(inst.xMin, inst.yMin, inst.zMin),
        new THREE.Vector3(inst.xMax, inst.yMax, inst.zMax),
      );
      localBox.applyMatrix4(mat4);
      box.union(localBox);
    }
    if (box.isEmpty()) return;

    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    const dist = maxDim * 1.8;

    camera.position.set(center.x + dist * 0.6, center.y + dist * 0.5, center.z + dist);
    camera.lookAt(center);
    camera.near = maxDim * 0.001;
    camera.far = maxDim * 100;
    camera.updateProjectionMatrix();
  }, [instances, camera]);

  return null;
}

export function AssemblyCanvas() {
  return (
    <Canvas
      camera={{ position: [10, 8, 10], fov: 45 }}
      style={{ width: '100%', height: '100%' }}
      gl={{
        preserveDrawingBuffer: true,
        powerPreference: 'high-performance',
        antialias: true,
        stencil: false,
      }}
    >
      <LocalEnvironment />
      <ambientLight intensity={0.35} />
      <directionalLight position={[10, 10, 5]} intensity={0.9} />
      <directionalLight position={[-8, 4, -6]} intensity={0.5} />

      <Suspense fallback={null}>
        {/* LOD 调度器：根据相机距离异步加载各实例的 GLB */}
        <LODController />
        {/* 渲染所有实例 */}
        <AssemblyViewer />
      </Suspense>

      <AutoFit />
      <CameraSetup />
    </Canvas>
  );
}
