# 3D 预览管线：STEP → GLB

> **迁移来源：** `CATIA-Copilot-PLM/docs/architecture/3d-preview-pipeline.md`  
> conversion 服务（`/conversion`）已原样迁入 plm-unified，本文档记录的 GLB 转换管线直接适用。

> 记录 STEP → GLB 转换管线的实现，包括 cadquery-ocp、pygltflib、包围盒解析和前端 GLTFLoader 集成。  
> 原对应 git branch: `fix/file-upload-npe-and-encoding`（CATIA-Copilot-PLM）

---

## 一、背景与问题

### 原有管线（OBJ + MTL）的缺陷

| 问题 | 根因 |
|------|------|
| 3D 预览全灰，无颜色 | FreeCAD 0.18 headless 模式下 `ViewObject` 为 None，无法读取 STEP 颜色；OBJ+MTL 路径推断机制脆弱 |
| 几何面片粗糙 | `Mesh.export()` 使用固定偏差值三角化，无法控制精度 |
| MTL 文件堆积 | 每次转换生成新 UUID 的 MTL，多次触发后附件越来越多 |
| 从主页进入 3D 预览为空 | 包围盒全 0，InstancesWorker 认为零件无尺寸，永远不加载 geometry |

### 最终方案

**STEP → GLB（binary glTF 2.0）单文件管线**

- 转换工具：`cadquery-ocp`（OpenCASCADE 7.8 Python 绑定）+ `pygltflib`
- OCC XDE (`XCAFDoc_ColorTool`) 在 headless 下读取 STEP 颜色，不依赖 GUI
- `BRepMesh_IncrementalMesh` 精度可控（相对弦差 5%）
- GLB 自包含几何 + 材质颜色，前端只需一次 XHR
- Three.js `GLTFLoader` 原生支持，PBR 光照正确

---

## 二、改动清单

### 2.1 转换服务（conversion-service）

#### `convert_step_glb.py`（新文件）

**路径：** `docdoku-plm-conversion-service/conversion-service/src/main/resources/.../step/convert_step_glb.py`

替换旧的 `convert_step_obj.py`，核心流程：

```
STEP → OCC XDE 读几何 + 颜色
     → BRepMesh_IncrementalMesh 三角化（deflection=0.05 相对弦差）
     → pygltflib 组装 GLB（每个 solid 独立 group + 材质）
     → 输出 {uuid}.glb，同时在 accessor 里写入正确的 min/max 包围盒
```

**已知注意点：**
- `to_face()` 是 OCP 的手动 downcast，依赖 `TShape()/Location()/Orientation()` 接口，升级 cadquery-ocp 时需验证
- 深层装配（>100 层嵌套）可能栈溢出（`collect_solid_colors` 递归），当前数据集不触发
- `doc` 必须由调用方持有（GC bug 修复：原版 `doc` 在 `read_step` 函数返回后立即被 GC，导致所有 TDF_Label 失效）

#### `StepFileConverterImpl.java`（修改）

**路径：** `docdoku-plm-conversion-service/conversion-service/src/main/java/.../converters/StepFileConverterImpl.java`

主要改动：
1. 调用 `convert_step_glb.py` 替换旧脚本，输出 `.glb`
2. **修复 stdout/stderr 串行读取死锁**：改用两个线程并发消费，防止大文件转换时进程挂起
3. `pythonInterpreter=null` 时给出明确错误信息
4. `conf.properties` 缺失时给出 SEVERE 日志而非 NPE 穿透 static initializer
5. `InterruptedException` catch 后恢复线程中断标志

#### `GeometryParser.java`（修改）

**路径：** `docdoku-plm-conversion-service/conversion-service/src/main/java/.../GeometryParser.java`

原版只支持 OBJ（扫描 `v x y z` 文本行）。新版：
- 按文件扩展名分发：`.glb` 走 `calculateBoxFromGlb()`，其他走原 OBJ 逻辑
- GLB 解析：读取 12 字节 header + JSON chunk，从所有 accessor 的 `min`/`max` 字段聚合全局包围盒
- OBJ 逻辑同时修复：支持 `v x y z`（单空格）和 `v  x y z`（双空格）两种格式

**已知注意点：**
- `extractMinMaxFromGltfJson` 会采样所有 accessor 的 min/max，不区分是否是 POSITION 类型（INDEX accessor 的 min/max 是整数索引，可能略微影响精度，但实际误差可忽略）

#### `conf.properties`（修改）

```
pythonInterpreter=/usr/bin/python3
freeCadLibPath=           # 废弃，保留兼容性
```

#### `Dockerfile.jvm`（修改）

**基础镜像迁移：**

| 旧 | 新 |
|----|----|
| `FROM openjdk:8-jre`（已下架） | `FROM debian:bookworm-slim` |
| `FROM fabric8/java-alpine-openjdk8-jre`（第三方，停止维护） | 本地 `COPY run-java.sh`（从 fabric8 提取） |
| Python 2.7 + FreeCAD 0.18（apt） | Python 3.11 + cadquery-ocp 7.8（离线 wheels） |

**离线 wheels（`docdoku-plm-conversion-service/wheels/`）：**

所有 Python 依赖打包在 repo 里，构建不依赖网络：
- `cadquery_ocp-7.8.1.1.post1-cp311-cp311-manylinux_2_31_x86_64.whl`（67 MB）
- `vtk-9.3.1-cp311-...whl`（88 MB，cadquery-ocp 运行时依赖）
- `matplotlib`、`numpy`、`pygltflib` 及其小依赖

---

### 2.2 前端（docdoku-plm-front）

#### `GLTFLoader.js`（新文件）

**路径：** `docdoku-plm-front/app/js/dmu/loaders/GLTFLoader.js`  
**路径：** `docdoku-plm-front/dist/js/dmu/loaders/GLTFLoader.js`（需同步）

Three.js r90 官方 GLTFLoader，包装为 AMD 模块：

```javascript
define(['threecore'], function (THREE) {
    THREE.GLTFLoader = ( function () { ... return GLTFLoader; } )();
    return THREE.GLTFLoader;   // AMD factory 返回构造函数
});
```

**注意：** `dist/js/dmu/loaders/` 目录需与 `app/js/dmu/loaders/` 手动同步（没有 npm build 流程）。`rebuild-front.sh` 脚本已自动处理此同步。

#### `LoaderManager.js`（修改）

**路径：** `docdoku-plm-front/app/product-structure/js/dmu/LoaderManager.js`

用 `GLTFLoader` 替换 `OBJLoader + MTLLoader`，`parseFile` 大幅简化：

```javascript
parseFile: function(filename, texturePath, callbacks) {
    var loader = new GLTFLoader();
    loader.load(filename,
        function(gltf) { var object = gltf.scene; setShadows(object); callbacks.success(object); },
        undefined,
        function(err) { callbacks.error && callbacks.error(err); }
    );
}
```

**已知注意点：**
- `XMLHttpRequest.prototype.open` monkey-patch 在多次实例化时会重复包装，目前只有单例使用，不触发问题
- `gltf.scene` 理论上可为 null（无 scene 的 glTF），目前我们的 GLB 总有 scene，不触发

#### `app/visualization/main.js`（修改）

添加 `gltfloader` 路径别名（与 product-structure 一致）。

#### `dist/` 文件（修改）

- `dist/visualization/main.js`：LoaderManager 模块替换 + gltfloader alias + urlArgs rev 更新
- `dist/product-structure/main.js`：LoaderManager 模块替换 + gltfloader alias + urlArgs rev 更新
- `dist/visualization/index.html`：`data-main` rev 参数更新（否则浏览器加载缓存旧版）
- `dist/product-structure/index.html`：同上

**注意：** 每次修改前端后需运行 `scripts/rebuild-front.sh`，它会自动更新 rev、同步 loaders、重建镜像。

#### `cad_instance_view.js`（修改，BUG-41）

`render()` 方法对 `tx/ty/tz/rx/ry/rz` 在显示前归零（`|v| < 1e-10`），避免 CATIA 浮点噪声（如 `-9.8e-15`）在固定宽度输入框里被截断为误导性数值。

---

### 2.3 构建脚本

#### `scripts/rebuild-conversion-service.sh`（新文件）

一键重建转换服务：
- 自动检查 API jar 依赖
- `mvn package` → `docker build` → `docker compose up`
- 支持 `--fast`（只热替换 jar，跳过镜像重建）和 `--deploy-only`

#### `scripts/rebuild-front.sh`（修改）

在构建前自动：
1. 同步 `app/js/dmu/loaders/` → `dist/js/dmu/loaders/`（包含 GLTFLoader）
2. 更新 `dist/*/index.html` 和 `dist/*/main.js` 的 `rev` 参数，强制浏览器加载新版本

---

## 三、Code Review 发现的问题

### 已修复

| 文件 | 问题 | 修复 |
|------|------|------|
| `StepFileConverterImpl.java` | stdout/stderr 串行读取，大文件时必然死锁 | 改用双线程并发消费 |
| `StepFileConverterImpl.java` | `pythonInterpreter=null` 时错误信息不明 | 加前置检查和明确异常消息 |
| `StepFileConverterImpl.java` | `conf.properties` 缺失时 NPE 穿透 static initializer | 加 null 检查 + SEVERE 日志 |
| `StepFileConverterImpl.java` | `InterruptedException` 后线程中断标志丢失 | 加 `Thread.currentThread().interrupt()` |
| `convert_step_glb.py` | `doc` GC 导致 TDF_Label 失效，`shape.IsNull()=true` | `read_step` 返回 `doc`，调用方持有 |

### 已记录、暂不修复

| 文件 | 问题 | 说明 |
|------|------|------|
| `convert_step_glb.py` | `to_face()` downcast 非 OCP 官方 API | 功能正常，升级依赖时需验证 |
| `convert_step_glb.py` | 深层装配递归可能栈溢出 | 当前数据集不触发，未来可改迭代 |
| `GeometryParser.java` | `extractMinMaxFromGltfJson` 采样所有 accessor | 实际误差可忽略 |
| `LoaderManager.js` | XHR prototype 重复 patch | 当前单例使用，不触发 |
| `LoaderManager.js` | `gltf.scene` 可为 null | 我们的 GLB 总有 scene |

---

## 四、遗留问题

### ConverterBean.java:172 的 checkout 检查

**问题：** 转换是异步的，若上传 stp 后立刻 checkin，回调时 `isCheckedOut()=false`，geometry 被丢弃。

**当前 workaround：** CATIA Copilot 软件在上传 stp 后等待转换完成（轮询 `conversion.succeed=true`）再 checkin。

**根本修复（方案 B，未实施）：**  
修改 `docdoku-plm-server/docdoku-plm-server-ejb/.../ConverterBean.java:172`，去除或放宽 `isCheckedOut()` 的强制要求。

---

## 五、Decimation（LOD 降采样）失效

Decimater 使用 `openMeshDecimater.sh` 处理 OBJ 格式，无法处理 GLB。目前日志会出现：  
`Decimation failed with code = 1 read error`

这不影响 3D 预览（LOD 0 = 原始精度），但多个 LOD 级别失效，大型装配体在远距离时不会降质量。暂未处理。

---

*最后更新：2026-06-13*
