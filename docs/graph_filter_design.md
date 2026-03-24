# Graph Filter 设计文档

## 1. 问题分析

### 当前实现的问题

`graph_filter.py` 使用 **BFS 子图展开** 算法：

```python
def _collect_reachable_nodes(self, start_indices: List[int]) -> Set[int]:
    reachable: Set[int] = set()
    queue: deque[int] = deque(start_indices)

    while queue:
        current = queue.popleft()
        if current in reachable:
            continue
        reachable.add(current)

        # 添加所有父节点
        for parent in parents:
            queue.append(parent)

        # 添加所有子节点
        for child in children:
            queue.append(child)

    return reachable
```

**问题：**

假设调用图如下：

```
[A] ──┐
      ├──► [Target] ──► [X]
[B] ──┘              │
                      └─► [Y]
```

当过滤 `Target` 时：
- 向上追踪：包含 `[A]` 和 `[B]`（所有父节点）
- 向下追踪：包含 `[X]` 和 `[Y]`（所有子节点）

如果 `[A]` 还调用了其他 50 个函数（`[A1]...[A50]`），这 50 个函数也会被包含进来，导致过滤后的图和完整图一样大。

### 用户需求

**路径切片**（Path Slice）而非子图展开：

**向上追踪规则：**
- ✅ 包含：`[Target]` → `[A]` → `[A的调用者]` → ...
- ❌ 不包含：`[A]` 的其他子节点（除了 `[Target]`）

**向下追踪规则：**
- ✅ 包含：`[Target]` → `[X]` → `[X的被调用者]` → ...
- ❌ 不包含：`[X]` 的其他父节点（除了 `[Target]`）

---

## 2. 新算法设计：路径切片

### 核心思想

1. **向上追踪**：沿调用链回溯，只保留调用路径上的节点
2. **向下追踪**：沿调用链展开，只保留被调用路径上的节点
3. **合并**：取两个方向的并集

### 算法伪代码

```python
class PathSliceFilter:
    def filter_by_function(self, target_name: str, max_depth: int = 5):
        """路径切片过滤"""

        # 1. 找到目标函数
        target_indices = self.name_to_indices.get(target_name)
        if not target_indices:
            raise ValueError(f"Function '{target_name}' not found")

        # 2. 向上追踪（寻找调用者链）
        upward_nodes = self._trace_upward(target_indices, max_depth)

        # 3. 向下追踪（寻找被调用链）
        downward_nodes = self._trace_downward(target_indices, max_depth)

        # 4. 合并两个方向的节点
        all_nodes = upward_nodes | downward_nodes

        # 5. 过滤并重新索引
        return self._filter_and_reindex(all_nodes)

    def _trace_upward(self, start_indices: List[int], max_depth: int) -> Set[int]:
        """
        向上追踪：沿调用链回溯

        策略：包含所有父节点（因为可能有多个调用者）
        """
        nodes = set(start_indices)

        # BFS 向上追踪，但限制深度
        for depth in range(max_depth):
            current_level_nodes = []

            for idx in nodes:
                # 找到调用当前函数的所有父节点
                parents = self.adjacency[idx][0]
                for parent in parents:
                    if parent not in nodes:
                        current_level_nodes.append(parent)

            if not current_level_nodes:
                break  # 没有更多父节点

            nodes.update(current_level_nodes)

        return nodes

    def _trace_downward(self, start_indices: List[int], max_depth: int) -> Set[int]:
        """
        向下追踪：沿调用链展开

        策略：包含所有子节点（因为可能调用多个函数）
        """
        nodes = set(start_indices)

        # BFS 向下追踪，但限制深度
        for depth in range(max_depth):
            current_level_nodes = []

            for idx in nodes:
                # 找到当前函数调用的所有子节点
                children = self.adjacency[idx][1]
                for child in children:
                    if child not in nodes:
                        current_level_nodes.append(child)

            if not current_level_nodes:
                break  # 没有更多子节点

            nodes.update(current_level_nodes)

        return nodes
```

### 算法改进：标记路径节点

为了更精确地控制边的包含，我们可以标记节点的"方向"：

```python
from enum import Enum, auto

class Direction(Enum):
    UPWARD = auto()      # 向上追踪的节点
    DOWNWARD = auto()    # 向下追踪的节点
    BOTH = auto()        # 双向都有

def filter_by_function_path_slice(self, target_name: str, max_depth: int = 5):
    """路径切片过滤，并标记节点方向"""

    target_indices = self.name_to_indices.get(target_name)
    if not target_indices:
        raise ValueError(f"Function '{target_name}' not found")

    # 标记节点方向
    node_directions: Dict[int, Direction] = {}

    # 目标节点标记为 BOTH
    for idx in target_indices:
        node_directions[idx] = Direction.BOTH

    # 向上追踪
    upward_nodes = self._trace_upward_with_direction(
        target_indices, max_depth, node_directions, Direction.UPWARD
    )

    # 向下追踪
    downward_nodes = self._trace_downward_with_direction(
        target_indices, max_depth, node_directions, Direction.DOWNWARD
    )

    # 过滤边：只保留方向匹配的边
    filtered_functions = self._filter_and_reindex_with_directions(
        node_directions
    )

    return filtered_functions
```

---

## 3. 实现方案

### 方案对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| **简单路径切片** | 实现简单，性能好 | 可能包含一些旁路节点 |
| **方向标记** | 更精确，可以过滤边 | 代码复杂度高 |
| **路径枚举** | 最精确，每条路径独立 | 可能路径爆炸 |

### 推荐：简单路径切片

对于大多数场景，简单路径切片已经足够：

```python
class GraphFilter:
    def __init__(self, functions: List[Dict[str, Any]], max_depth: int = 5):
        self.functions = functions
        self.max_depth = max_depth
        self.name_to_indices = self._build_name_map()
        self.adjacency = self._build_adjacency_map()

    def filter_by_function(self, target_name: str) -> List[Dict[str, Any]]:
        """路径切片过滤"""
        target_indices = self.name_to_indices.get(target_name)
        if not target_indices:
            raise ValueError(f"Function '{target_name}' not found")

        # 向上追踪（调用者链）
        upward_nodes = self._trace_upward(target_indices)

        # 向下追踪（被调用链）
        downward_nodes = self._trace_downward(target_indices)

        # 合并
        all_nodes = upward_nodes | downward_nodes

        return self._filter_and_reindex(all_nodes)

    def _trace_upward(self, start_indices: List[int]) -> Set[int]:
        """向上追踪，限制深度"""
        nodes = set(start_indices)

        for depth in range(self.max_depth):
            frontier = []
            for idx in nodes:
                parents = self.adjacency[idx][0]
                for parent in parents:
                    if parent not in nodes:
                        frontier.append(parent)

            if not frontier:
                break
            nodes.update(frontier)

        return nodes

    def _trace_downward(self, start_indices: List[int]) -> Set[int]:
        """向下追踪，限制深度"""
        nodes = set(start_indices)

        for depth in range(self.max_depth):
            frontier = []
            for idx in nodes:
                children = self.adjacency[idx][1]
                for child in children:
                    if child not in nodes:
                        frontier.append(child)

            if not frontier:
                break
            nodes.update(frontier)

        return nodes
```

---

## 4. 深度限制

### 默认深度

```python
DEFAULT_MAX_DEPTH = 5
```

### 可配置深度

```python
# cli.py 添加参数
parser.add_argument(
    '--filter-depth',
    type=int,
    default=5,
    help='Max depth for path slice filtering (default: 5)'
)
```

---

## 5. 测试用例

### 用例 1：简单调用链

```
[A] ──► [Target] ──► [B]
```

过滤 `[Target]`，max_depth=1：
- 向上：`[A]`
- 向下：`[B]`
- 结果：`[A], [Target], [B]`

### 用例 2：多父节点

```
[A] ──┐
      ├──► [Target] ──► [B]
[C] ──┘
```

过滤 `[Target]`，max_depth=1：
- 向上：`[A], [C]`
- 向下：`[B]`
- 结果：`[A], [C], [Target], [B]`

### 用例 3：深度限制

```
[L1] ──► [L2] ──► [Target] ──► [D2] ──► [D3]
```

过滤 `[Target]`，max_depth=2：
- 向上：`[L2], [L1]`
- 向下：`[D2]`
- 结果：`[L1], [L2], [Target], [D2]`

---

## 6. 实现优先级

1. ✅ **立即实现**：简单路径切片（替换当前 BFS 算法）
2. ⏸️ **后续考虑**：方向标记和边过滤
3. ⏸️ **优化**：添加深度配置参数

---

## 7. 预期效果

**修复前：**
```bash
./run.sh --filter-func "InputHandler::processEvent"
# 输出: testgraph.json (1500 个函数)
# 输出: testgraph_InputHandler...json (1450 个函数) ← 几乎一样
```

**修复后：**
```bash
./run.sh --filter-func "InputHandler::processEvent"
# 输出: testgraph.json (1500 个函数)
# 输出: testgraph_InputHandler...json (50 个函数) ← 只有相关路径
```

---

## 8. 风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 丢失重要节点 | 低 | 中 | 提供深度配置参数 |
| 性能下降 | 低 | 低 | BFS 复杂度仍为 O(V+E) |
| 用户不适应 | 中 | 低 | 文档说明 + 默认深度 5 |
