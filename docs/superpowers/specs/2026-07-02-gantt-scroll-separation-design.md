# 甘特图横向滚动分离 & 视图切换对齐方案

## 背景

当前甘特图（`GanttView.tsx`）的布局是将左侧固定列（任务编号、任务名称、负责人、状态）和右侧日历时间轴放在同一个 `overflow: auto` 容器中，左侧通过 `position: sticky; left: 0` 吸附。这导致整体横向滚动时左侧列也会"漂移"，体验不够稳定。

同时，计划表（`Projects.tsx` 中的 `<table>`）和甘特图虽然列宽数值一致，但布局方式不同（表格 `table-fixed` vs flexbox），切换视图时存在微小视觉跳动。

## 目标

1. **日历独立横向滚动**：右侧日历部分单独放入 `overflow-x: auto` 容器，左侧四列完全固定不参与横向滚动
2. **纵向同步滚动**：左右两侧共享同一个外层纵向滚动容器，上下滚动同步
3. **视图切换像素级对齐**：计划表与甘特图切换时，左侧四列位置、宽度、样式完全一致，无视觉跳动

## 设计方案

### 架构

```
┌─ 外层容器 (border rounded-lg overflow-hidden) ────────────────┐
│ ┌─ overflow-y:auto; max-height:70vh ──────────────────────────┐ │  ← 纵向滚动容器
│ │ ┌─ flex ────────────────────────────────────────────────────┐ │ │
│ │ │ ┌─ SharedLeftPanel (574px) ┐ ┌─ overflow-x:auto ────────┐ │ │ │
│ │ │ │ 任务编号│名称│负责人│状态│ │ 甘特图日历 / 计划表其他列│ │ │ │
│ │ │ │ ← 计划表&甘特图共享 →    │ │ ← 各自独立渲染           │ │ │ │
│ │ │ └─────────────────────────┘ └───────────────────────────┘ │ │ │
│ │ └───────────────────────────────────────────────────────────┘ │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 改动点

#### 1. 新增 `SharedLeftPanel.tsx` 组件

**位置**：`frontend/src/pages/Project/SharedLeftPanel.tsx`

**职责**：渲染左侧四列的表头和数据行，同时被计划表和甘特图使用。

**Props**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `visibleTasks` | `GanttTask[]` | 可见任务列表（已根据展开状态过滤） |
| `expanded` | `Set<string>` | 展开的任务 ID 集合 |
| `onToggleExpand` | `(taskId: string) => void` | 展开/折叠回调 |
| `onRowClick` | `(taskId: string) => void` | 点击行回调 |
| `hoveredId` | `string \| null` | 当前悬停的任务 ID（甘特图专用，计划表传 null） |
| `onHover` | `(taskId: string \| null) => void` | 悬停回调（甘特图专用） |
| `project` | `{ code, name, status, owner_name } \| null` | 项目汇总行数据 |
| `childMap` | `Record<string, GanttTask[]>` | 父子映射（判断是否有子任务） |

**渲染内容**：

- **表头行**：`任务编号(200px)` | `任务名称(flex)` | `负责人(72px)` | `状态(64px)`
- **项目汇总行**（`hasProject` 时）
- **任务数据行**：复用现有 `TaskCodeCell`、`TaskNameCell`、`TaskAssigneeCell`，状态标签统一渲染

#### 2. 修改 `GanttView.tsx`

- 移除左侧面板的 `sticky left-0`
- 将左侧面板替换为 `<SharedLeftPanel>`
- 右侧日历部分包裹 `<div className="overflow-x-auto">` 实现独立横向滚动
- `scrollRef` 仅用于拖拽平移（`scrollLeft` 改为操作右侧面板的 ref）
- 外层增加 `overflow-y: auto` 纵向滚动容器

**甘特图模式布局**：
```tsx
<div className="border border-gray-200 rounded-lg overflow-hidden">
  <div className="overflow-y-auto" style={{ maxHeight: '70vh' }}>
    <div className="flex">
      <SharedLeftPanel {...leftProps} onHover={setHoveredId} hoveredId={hoveredId} />
      <div className="overflow-x-auto flex-1" ref={calendarScrollRef}>
        <div style={{ width: chartW }}>
          {/* 日历表头 + SVG */}
        </div>
      </div>
    </div>
  </div>
</div>
```

#### 3. 修改 `Projects.tsx` 计划表视图

- 左侧四列替换为 `<SharedLeftPanel>`
- 右侧其他列（优先级、计划开始、计划完成、关联/操作）包裹在 `<div className="overflow-x-auto flex-1">` 中
- 外层使用相同的 `overflow-y: auto` 纵向滚动容器结构

**计划表模式布局**：
```tsx
<div className="border border-gray-200 rounded-lg overflow-hidden">
  <div className="overflow-y-auto" style={{ maxHeight: '70vh' }}>
    <div className="flex">
      <SharedLeftPanel {...leftProps} />
      <div className="overflow-x-auto flex-1">
        <table className="table-fixed w-full">
          {/* 优先级 / 计划开始 / 计划完成 / 关联操作 */}
        </table>
      </div>
    </div>
  </div>
</div>
```

### 关键常量和样式

| 常量 | 值 | 来源 |
|------|-----|------|
| `ROW_H` | 36px | `ganttUtils.ts` |
| `CODE_W` | 200px | `ganttUtils.ts` |
| `ASSIGNEE_W` | 72px | `ganttUtils.ts` |
| `STATUS_W` | 64px | `ganttUtils.ts` |
| `LEFT_W` | 574px | `ganttUtils.ts` (=200+238+72+64) |
| `INDENT` | 20px | `ganttUtils.ts` |
| 最大高度 | 70vh | 现有值，保持不变 |

### 拖拽平移适配

甘特图现有拖拽平移功能（`onPanDown`）通过调整 `scrollRef.current.scrollLeft` 实现。改动后需要将 `scrollRef` 替换为日历容器的 ref（`calendarScrollRef`），操作其 `scrollLeft`。

### 甘特图横向滚动条可见性

右层面板的 `overflow-x: auto` 会在内容宽度超出容器时显示横向滚动条。如果内容高度超过 `70vh`，用户需纵向滚到底才能看到横向滚动条。可以通过以下方式优化：
- 方案 a：在纵向滚动容器的 `padding-bottom` 预留横向滚动条空间
- 方案 b：右侧面板增加轻微 `padding-bottom` 使横向滚动条上移
- 方案 c：保持默认行为（用户习惯纵向滚动到底操作时间轴也是合理的）

## 改动文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `frontend/src/pages/Project/SharedLeftPanel.tsx` | **新增** | 共享左侧四列组件 |
| `frontend/src/pages/Project/gantt/GanttView.tsx` | 修改 | 替换左列为 SharedLeftPanel，分离横向滚动 |
| `frontend/src/pages/Project/Projects.tsx` | 修改 | 替换计划表左列为 SharedLeftPanel，统一容器结构 |

## 不涉及改动

- `ganttUtils.ts` — 常量已标准化，无需改动
- `TaskRowCells.tsx` — 细胞组件继续复用，无需改动
- 自动排期、拖拽任务条、依赖箭头等甘特图核心交互逻辑 — 保持不变
- `types/project.ts` — 类型定义不变

## 验证清单

- [ ] 甘特图日历部分可独立横向滚动，左侧四列固定不动
- [ ] 左右纵向滚动同步（共用外层滚动容器，自然同步）
- [ ] 计划表 ↔ 甘特图切换时，左侧四列像素级对齐，无跳动
- [ ] 甘特图拖拽平移（Pan）功能正常
- [ ] 甘特图任务拖拽、调整、依赖线等交互正常
- [ ] 表头纵向固定（甘特图日历表头、计划表表头）
- [ ] 项目汇总行在两种视图下渲染一致
