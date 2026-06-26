# 3D 预览参数调整手册

> **迁移来源：** `CATIA-Copilot-PLM/docs/reference/3d-preview-tuning.md`  
> 转换服务部分（PBR 材质、三角化精度、convert_step_glb.py）直接适用于 plm-unified/conversion。  
> 前端部分（SceneManager.js、LoaderManager.js）适用于 plm-unified/frontend（myPDM React 已集成 Three.js）。

> 说明如何手动调整 3D 预览的光照、边线、动画、相机、材质、网格精度等参数。  
> 适用于 STEP→GLB 转换服务（`/conversion`）和前端 Three.js 查看器（`/frontend`）。

---

## 一、参数分布概览

| 分类 | 文件 | 说明 |
|------|------|------|
| 场景光照 | `SceneManager.js` | 直射光、半球光强度与颜色 |
| 边线渲染 | `SceneManager.js` | 边线角度阈值与颜色 |
| 相机动画 | `SceneManager.js`、`visualization/main.js` | 动画时长与缓动函数 |
| 控制器速度 | `product-structure/main.js`、`visualization/main.js` | 旋转/缩放/平移速度 |
| 场景选项 | `product-structure/main.js`、`visualization/main.js` | 近/远裁剪面、默认相机位置 |
| PBR 材质 | `convert_step_glb.py` | 金属度、粗糙度 |
| 三角化精度 | `convert_step_glb.py` | 弦偏差、角度偏差 |
| 预定义颜色 | `convert_step_glb.py` | ISO 预定义颜色 RGB 映射 |

---

## 二、场景光照（SceneManager.js）

**文件路径：** `docdoku-plm-front/app/product-structure/js/dmu/SceneManager.js`

光照在 `addLightsToCamera` 函数中配置（约第 155–192 行）。场景使用两盏直射光 + 一盏半球光：

### 2.1 主直射光（dirLight1）

```javascript
// dirLight1 — 从右上前方照射
var dirLight1 = new THREE.DirectionalLight(App.SceneOptions.cameraLight1Color, 0.6);
dirLight1.position.set(200, 200, 1000).normalize();
```

| 参数 | 当前值 | 调整方向 |
|------|--------|----------|
| 强度 | `0.6` | 升高 → 更亮；降低 → 更暗 |
| 颜色 | 由 `cameraLight1Color` 决定（见第四节） | 改 SceneOptions 的颜色值 |
| 方向 | `set(200, 200, 1000)` 后 normalize | 调 xyz 比例改变光源角度 |

### 2.2 辅助直射光（dirLight2）

```javascript
// dirLight2 — 从左前上方补光，带阴影
var dirLight2 = new THREE.DirectionalLight(App.SceneOptions.cameraLight2Color, 0.3);
dirLight2.color.setHSL(0.1, 0.3, 0.85);   // ← 此行会覆盖上方颜色
dirLight2.position.set(-1, 1.75, 1).multiplyScalar(50);
dirLight2.castShadow = true;
dirLight2.shadow.mapSize.width  = 2048;
dirLight2.shadow.mapSize.height = 2048;
dirLight2.shadow.camera.far     = 3500;
dirLight2.shadow.bias           = -0.0001;
```

| 参数 | 当前值 | 说明 |
|------|--------|------|
| 强度 | `0.3` | 补光，不宜过高，否则阴影区过亮 |
| HSL 色调 | `(0.1, 0.3, 0.85)` | hue=0.1 偏暖橙，saturation=0.3，lightness=0.85 |
| 阴影贴图 | `2048 × 2048` | 更大 → 阴影更清晰，但更耗显存 |
| shadow.bias | `-0.0001` | 负值修复阴影偏移（shadow acne），如有条纹可调小 |

> **注意：** `dirLight2.color.setHSL(...)` 这一行会覆盖从 `cameraLight2Color` 读取的值。如果要通过 SceneOptions 控制 dirLight2 颜色，需将此行删除。

### 2.3 半球光（hemiLight）

```javascript
var hemiLight = new THREE.HemisphereLight(App.SceneOptions.ambientLightColor, App.SceneOptions.ambientLightColor, 0.3);
hemiLight.color.setHSL(0.6, 0.5, 0.5);        // 天空色：蓝色系
hemiLight.groundColor.setHSL(0.095, 0.5, 0.4); // 地面色：橙黄色
hemiLight.position.set(0, 0, 500);
```

| 参数 | 当前值 | 说明 |
|------|--------|------|
| 强度 | `0.3` | 使暗面有基础亮度；值过高会让场景"发灰" |
| 天空色 HSL | `(0.6, 0.5, 0.5)` | hue=0.6 蓝，影响模型顶部受光区 |
| 地面色 HSL | `(0.095, 0.5, 0.4)` | hue=0.095 橙黄，影响模型底部阴影区 |

> **调整建议：** 如整体过亮，优先降低 `hemiLight` 强度（`0.3 → 0.2`）；如阴影区太暗，升高地面色 lightness（`0.4 → 0.5`）。

---

## 三、边线渲染（SceneManager.js）

边线通过 Three.js `EdgesGeometry` 叠加在每个 Mesh 上，约在第 630–640 行的 `loadMeshBuffer` 函数中添加：

```javascript
// 边线叠加层
var edgesGeo  = new THREE.EdgesGeometry(bufferGeometry, 30);   // 阈值角 30°
var edgeMat   = new THREE.LineBasicMaterial({
    color:     0x222222,
    linewidth: 1
});
var edgeLines = new THREE.LineSegments(edgesGeo, edgeMat);
mesh.add(edgeLines);
```

| 参数 | 当前值 | 调整效果 |
|------|--------|----------|
| `thresholdAngle` | `30`（度） | 减小 → 边线更多（甚至出现三角面纹路）；增大 → 仅保留轮廓线 |
| `color` | `0x222222`（深灰） | 改为 `0x000000` 更黑；改为 `0x888888` 更浅 |
| `linewidth` | `1` | WebGL 通常不支持 >1，修改无效 |

> **性能提示：** `thresholdAngle` 越小，生成的线段越多，在面数较多的模型上会有明显性能消耗。推荐范围 `15°~45°`。

---

## 四、场景选项与控制器速度

### 4.1 产品结构入口（product-structure/main.js）

**文件路径：** `docdoku-plm-front/app/product-structure/main.js`（约第 139–152 行）

```javascript
App.SceneOptions = {
    grid:                    false,
    zoomSpeed:               1.2,
    rotateSpeed:             1.0,
    panSpeed:                0.3,
    cameraNear:              0.1,       // 近裁剪面（单位 mm）
    cameraFar:               5E4,       // 远裁剪面
    defaultCameraPosition:   {x: -1000, y: -1000, z: 1000},
    defaultTargetPosition:   {x: 0, y: 0, z: 0},
    ambientLightColor:       0x888888,  // 半球光/环境光颜色
    cameraLight1Color:       0x888888,  // 主直射光颜色（实际被 HSL 覆盖）
    cameraLight2Color:       0xaaaaaa,  // 辅直射光颜色（实际被 HSL 覆盖）
    transformControls:       true       // 允许拖拽变换零件位置
};
```

### 4.2 零件可视化入口（visualization/main.js）

**文件路径：** `docdoku-plm-front/app/visualization/main.js`（约第 96–109 行）

```javascript
App.SceneOptions = {
    grid:                    false,
    zoomSpeed:               1.2,
    rotateSpeed:             1.0,
    panSpeed:                0.3,
    cameraNear:              1,         // 注意：比 product-structure 更远
    cameraFar:               5E4,
    defaultCameraPosition:   {x: -1000, y: -1000, z: 1000},
    defaultTargetPosition:   {x: 0, y: 0, z: 0},
    ambientLightColor:       0x888888,
    cameraLight1Color:       0x888888,
    cameraLight2Color:       0xaaaaaa,
    transformControls:       false      // 仅查看，不允许变换
};
```

### 4.3 参数说明

| 参数 | 说明 | 调整建议 |
|------|------|----------|
| `zoomSpeed` | 鼠标滚轮缩放倍率 | 增大 → 缩放更灵敏；默认 `1.2` |
| `rotateSpeed` | 鼠标拖拽旋转倍率 | 增大 → 旋转更快；默认 `1.0` |
| `panSpeed` | 右键/中键平移倍率 | 增大 → 平移更快；默认 `0.3` |
| `cameraNear` | 相机近裁剪距离（mm） | 太大 → 靠近时模型被截断；太小 → 深度精度下降 |
| `cameraFar` | 相机远裁剪距离（mm） | 默认 `50000`，超出此距离的模型不可见 |
| `defaultCameraPosition` | 初始化时相机位置 | 调整 xyz 改变初始视角 |
| `ambientLightColor` | 传入半球光的基础颜色，会被 HSL 覆盖 | 影响不大，保持灰色即可 |

---

## 五、相机动画与最佳适配距离

### 5.1 动画时长

| 入口 | 参数位置 | 当前值 | 说明 |
|------|----------|--------|------|
| product-structure | `SceneManager.js` `cameraAnimation()` 调用处 | `1000` ms | flyTo / lookAt / bestFitView 动画 |
| product-structure | `SceneManager.js` `resetCameraPlace()` 调用处 | `1000` ms | 重置相机动画 |
| product-structure | `SceneManager.js` `cancelTransformation()` | `2000` ms | 取消编辑时对象回位动画（单独的） |
| visualization | `visualization/main.js` `_vizFit` 调用处 | `1000` ms | bestFit 动画 |
| visualization | `visualization/main.js` `_vizReset` 调用处 | `1000` ms | 重置视角动画 |

搜索方式：全文搜索 `cameraAnimation(` 或 `applyCamera(` 找到调用处，修改第二个参数（毫秒数）。

### 5.2 缓动函数

两个入口均使用 `TWEEN.Easing.Quintic.InOut`，即五次方先加速后减速。可替换为：

```javascript
TWEEN.Easing.Cubic.InOut    // 更平缓
TWEEN.Easing.Linear.None    // 匀速（用于重置动画）
TWEEN.Easing.Bounce.Out     // 弹簧效果（一般不推荐）
```

### 5.3 最佳适配距离（getFitDistance）

**visualization/main.js** 约第 199–202 行：

```javascript
function getFitDistance(maxDimension) {
    var fov = camera.fov * Math.PI / 180;
    return (maxDimension / 2) / Math.tan(fov / 2) * 1.8;
}
```

| 参数 | 当前值 | 说明 |
|------|--------|------|
| padding 系数 | `1.8` | 最终距离 = 理论最小距离 × 1.8；增大 → 模型看起来更小；减小 → 模型更充满视口 |

**SceneManager.js** bestFitView（约第 1293 行）：

```javascript
var distance = Math.max(size.x, size.y, size.z) * 2;
```

包围盒最大边长 × 2 作为相机距离。系数 `2` 越大模型越小，越小模型越充满视口（不能小于 `cameraNear`）。

---

## 六、PBR 材质参数（convert_step_glb.py）

**文件路径：** `docdoku-plm-conversion-service/conversion-service/src/main/resources/com/docdoku/plm/conversion/service/converters/step/convert_step_glb.py`

材质参数在 `build_glb()` 函数中（约第 411–419 行）：

```python
material = pygltflib.Material(
    pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
        baseColorFactor=[r, g, b, 1.0],   # STEP 解析出的颜色
        metallicFactor=0.05,               # 金属度
        roughnessFactor=0.7,               # 粗糙度
    ),
    doubleSided=True,                      # 双面渲染
)
```

| 参数 | 当前值 | 调整效果 |
|------|--------|----------|
| `metallicFactor` | `0.05` | 范围 0~1；增大 → 更有金属质感（高光窄而亮）；减小 → 更像塑料/陶瓷 |
| `roughnessFactor` | `0.7` | 范围 0~1；增大 → 更哑光；减小 → 更光滑有镜面反射 |
| `doubleSided` | `True` | `False` 可节省渲染调用，但薄壁/曲面背面会穿透消失 |

> **组合建议：**
> - 机加工金属零件：`metallic=0.6, roughness=0.3`
> - 注塑塑料零件：`metallic=0.0, roughness=0.8`
> - 当前默认（通用）：`metallic=0.05, roughness=0.7`

### 6.1 默认颜色

```python
DEFAULT_COLOR = (0.8, 0.8, 0.8)   # 第 83 行，无颜色信息时使用浅灰色
```

### 6.2 ISO 预定义颜色映射（第 138–150 行）

当 STEP 文件使用 `DRAUGHTING_PRE_DEFINED_COLOUR` 时，会查此表：

| 名称 | RGB |
|------|-----|
| white | `(1.000, 1.000, 1.000)` |
| black | `(0.000, 0.000, 0.000)` |
| red | `(1.000, 0.000, 0.000)` |
| green | `(0.000, 0.502, 0.000)` |
| blue | `(0.000, 0.000, 1.000)` |
| yellow | `(1.000, 1.000, 0.000)` |
| cyan | `(0.000, 1.000, 1.000)` |
| magenta | `(1.000, 0.000, 1.000)` |
| light_grey | `(0.800, 0.800, 0.800)` |
| medium_grey | `(0.502, 0.502, 0.502)` |
| dark_grey | `(0.204, 0.204, 0.204)` |

修改此表可调整 CATIA 预定义颜色在 3D 预览中的实际显示颜色。

---

## 七、三角化精度（convert_step_glb.py）

精度参数通过命令行传入（第 56–64 行），也可修改脚本内默认值：

```python
parser.add_argument('--deflection', type=float, default=0.05)  # 弦偏差
parser.add_argument('--angular',    type=float, default=0.3)   # 角度偏差（弧度）
```

| 参数 | 默认值 | 说明 | 精度/文件大小权衡 |
|------|--------|------|------------------|
| `deflection` | `0.05` | 相对弦偏差，控制曲面三角化密度 | 减小 → 更精细，文件更大 |
| `angular` | `0.3`（≈17°） | 角度偏差（弧度），控制曲率变化处的采样 | 减小 → 曲率处更圆滑 |

**推荐取值范围：**

| 用途 | deflection | angular |
|------|-----------|---------|
| 快速预览（低精度） | `0.1` | `0.5` |
| 默认（平衡） | `0.05` | `0.3` |
| 高精度展示 | `0.01` | `0.1` |

---

## 八、修改后的部署流程

### 8.1 前端修改（光照/边线/动画/控制器参数）

修改以下任一文件后，需重建并部署前端：

- `docdoku-plm-front/app/product-structure/js/dmu/SceneManager.js`
- `docdoku-plm-front/app/product-structure/main.js`
- `docdoku-plm-front/app/visualization/main.js`

**部署命令：**

```bash
cd /home/chenweibo/CATIA-Copilot-PLM
bash scripts/rebuild-front.sh
```

脚本会自动完成：`npm build` → Docker 镜像构建 → 容器重启 → rev 参数更新（强制浏览器缓存失效）→ 三层校验（dist / 容器内 / HTTP 返回）。

整个流程约 **30~60 秒**。

### 8.2 转换服务修改（PBR 材质/三角化精度/颜色映射）

修改 `convert_step_glb.py` 后，使用 `--fast` 模式热替换 jar（无需 Docker 网络，本地 Maven 构建后替换容器内 jar）：

```bash
cd /home/chenweibo/CATIA-Copilot-PLM
bash scripts/rebuild-conversion-service.sh --fast
```

`--fast` 模式执行步骤：
1. 本地 `mvn package -DskipTests`（约 20 秒）
2. 将新 jar 复制到运行中的容器
3. 重启容器内 Spring Boot 进程

> **注意：** `--fast` 不重建 Docker 镜像，只热替换 jar。适合迭代调参，正式发布前应执行完整构建。

### 8.3 重新转换已有 STEP 文件

材质或三角化参数修改后，旧 GLB 文件不会自动更新。需删除旧缓存并重新触发转换：

```bash
# 进入容器（或通过管理界面触发转换）
docker exec -it docdoku-plm-docker-conversion-1 bash

# 删除指定零件的 GLB 缓存（替换 <uuid> 为实际文件名）
rm /var/docdoku/vault/<workspace>/<uuid>.glb

# 在 PLM 界面重新上传或重新触发转换即可
```

---

## 九、参数快查表

### 光照快查

| 效果目标 | 调整点 | 参考值 |
|---------|--------|--------|
| 整体过亮 | `hemiLight` 强度 ↓ | `0.3 → 0.2` |
| 整体过暗 | `dirLight1` 强度 ↑ | `0.6 → 0.8` |
| 阴影区死黑 | `hemiLight.groundColor` lightness ↑ | `0.4 → 0.5` |
| 偏冷/偏暖 | `dirLight2` HSL hue | `0.0`=红，`0.6`=蓝 |
| 阴影有条纹 | `shadow.bias` 调小 | `-0.0001 → -0.0005` |

### 边线快查

| 效果目标 | 调整点 | 参考值 |
|---------|--------|--------|
| 边线太多/乱 | `thresholdAngle` ↑ | `30 → 45` |
| 轮廓线太少 | `thresholdAngle` ↓ | `30 → 15` |
| 边线颜色太深 | `edgeLines color` | `0x222222 → 0x666666` |
| 关闭边线 | 注释掉 `mesh.add(edgeLines)` | — |

### 动画快查

| 效果目标 | 调整点 | 参考值 |
|---------|--------|--------|
| 动画太慢 | duration ↓ | `1000 → 600` ms |
| 动画太快/跳帧感 | duration ↑ | `1000 → 1500` ms |
| 动画抖动 | 改用 `Cubic.InOut` 缓动 | — |

### 材质快查

| 效果目标 | 调整点 | 参考值 |
|---------|--------|--------|
| 太哑光 | `roughnessFactor` ↓ | `0.7 → 0.4` |
| 太亮/镜面感强 | `roughnessFactor` ↑ | `0.7 → 0.9` |
| 塑料感不够 | `metallicFactor` ↓ | `0.05 → 0.0` |
| 金属感 | `metallicFactor` ↑ | `0.05 → 0.5` |

---

*最后更新：2026-06-14*
