# 餐桌状态检测逻辑

## 目的

检测并追踪餐桌状态，为数据驱动的运营洞察提供支持。系统通过计算机视觉实时监控每张桌子的占用状态，为分析服务质量、菜单有效性和顾客行为奠定基础。

## 核心业务问题

我们希望测量顾客入座到下单的时间间隔。过长的延迟（5-10分钟以上）可能表明：
- 菜单设计混乱或复杂
- 服务员关注不足
- 顾客体验不佳

通过视觉检测餐桌状态转换并与POS系统的点单时间戳关联，我们可以识别点餐流程中的摩擦点。

---

## 状态机设计

### 4个状态

每张餐桌处于4个互斥状态之一：

| 状态 | 条件 | 视觉指标 | 持续时间缓冲 | 颜色 |
|------|------|---------|-------------|------|
| **IDLE（空闲）** | 桌旁无人 | 餐桌区域空置 | 1秒 | 绿色 (GREEN) |
| **OCCUPIED（使用中）** | 仅有顾客 | 顾客坐着/站立 | 1秒 | 黄色 (YELLOW) |
| **SERVING（服务中）** | 顾客+服务员 | 双方同时在场 | 1秒 | 橙色 (ORANGE) |
| **CLEANING（清理中）** | 仅有服务员（无顾客）| 服务员清理/擦桌 | 1秒 | 蓝色 (BLUE) |

### 状态转换

```
IDLE → OCCUPIED → SERVING ⟷ OCCUPIED → CLEANING → IDLE
```

**详细流程：**

1. **IDLE → OCCUPIED**
   - 顾客进入餐桌ROI区域
   - 必须保持稳定1秒以上以避免误触发
   - 记录 `session_start_time`（会话开始时间）

2. **OCCUPIED ⟷ SERVING**
   - OCCUPIED → SERVING：服务员接近餐桌（1秒缓冲）
   - SERVING → OCCUPIED：服务员离开餐桌（1秒缓冲）
   - 双向转换（每个会话期间可发生多次）

3. **OCCUPIED → CLEANING**
   - 所有顾客离开餐桌区域
   - 服务员出现并停留1秒以上
   - 记录 `session_end_time`（会话结束时间）

4. **CLEANING → IDLE**
   - 服务员完成清理并离开（1秒缓冲）
   - 餐桌准备好迎接下一批顾客
   - 重置所有会话数据

---

## 检测逻辑

### 输入要求

1. **ROI配置**（手动标注）
   - 餐桌边界框 (x1, y1, x2, y2)
   - 座位区域多边形（可选，用于精确判断）
   - 餐桌容量（座位数）

2. **YOLO检测输出**
   - 带有track_id的人员边界框
   - 分类：`customer`（顾客）或 `waiter`（服务员）
   - 置信度分数

### 处理流程

```python
对于每一帧：
  1. 检测画面中所有人员（YOLOv8m）
  2. 筛选餐桌ROI内的人员
  3. 分类为顾客或服务员（YOLO11n-cls）
  4. 统计：customers_present（顾客数量）, waiters_present（服务员数量）
  5. 根据计数更新状态机
```

### 状态判定规则

```
if customers_present == 0 and waiters_present == 0:
    state = IDLE（1秒缓冲后）

elif customers_present > 0 and waiters_present == 0:
    state = OCCUPIED（1秒缓冲后）

elif customers_present > 0 and waiters_present > 0:
    state = SERVING（1秒缓冲后）

elif customers_present == 0 and waiters_present > 0:
    state = CLEANING（1秒缓冲后）
```

---

## 边缘情况与解决方案

### 1. 顾客临时离开（上厕所）

**问题**：所有顾客上厕所2-3分钟 → 餐桌看起来空了

**解决方案**：
- OCCUPIED → CLEANING 需要餐桌空置3分钟以上
- 必须检测到60秒窗口内有服务员活动
- 短暂缺席（<3分钟）保持OCCUPIED状态

### 2. 服务员路过/上菜

**问题**：顾客用餐时服务员短暂出现 → 触发SERVING

**解决方案**：
- SERVING状态是有意且正确的（代表服务互动）
- 服务员离开后立即转回OCCUPIED
- 对会话计时无负面影响

### 3. 部分顾客离开

**问题**：4人桌中2人提前离开，剩余2人继续用餐

**解决方案**：
- 跟踪人数历史变化
- 只要有任何顾客在场，会话继续
- 仅当所有顾客离开3分钟以上才结束会话

### 4. 快速翻台

**问题**：新顾客在清理前/清理期间到达

**解决方案**：
- 如果在CLEANING期间检测到顾客：
  - 立即关闭上一个会话
  - 用新顾客ID开始新会话
- 通过POS时间戳进行人工验证

### 5. 服务员快速清理（<3秒）

**问题**：服务员2秒内拿走盘子就走 → 漏检

**解决方案**：
- 使用60秒滑动窗口
- 累计所有服务员出现次数（多次快速访问）
- 如果60秒内累计时间 ≥3秒 → 确认CLEANING

---

## 关键时间戳

### 每个会话

| 事件 | 时间戳 | 检测方式 |
|------|--------|---------|
| **入座时间** | `session_start_time` | 首次检测到顾客 + 5秒稳定 |
| **服务开始** | `first_serving_time` | 首次转换到SERVING状态 |
| **会话结束** | `session_end_time` | 餐桌空置3分钟 + 服务员活动 |

### 衍生指标

```python
# 从入座到下单的时间（需要POS数据）
order_delay = pos_order_time - session_start_time

# 会话持续时间
session_duration = session_end_time - session_start_time

# 服务互动频率
service_count = SERVING状态转换次数
```

---

## 配置参数

### 可调阈值

| 参数 | 默认值 | 范围 | 用途 |
|------|--------|------|------|
| `SETTLE_THRESHOLD` | 60秒 | 30-120秒 | OCCUPIED状态的最小稳定时间 |
| `LEAVE_THRESHOLD` | 180秒 | 120-300秒 | 判定离开的最小空置时间 |
| `CLEANING_MIN_WAITER_TIME` | 3秒 | 2-5秒 | CLEANING状态的最小服务员停留时间 |
| `CLEANING_WINDOW` | 60秒 | 30-120秒 | 累计服务员活动的时间窗口 |
| `PERSON_CONF_THRESHOLD` | 0.3 | 0.2-0.5 | YOLO人员检测置信度 |
| `STAFF_CONF_THRESHOLD` | 0.5 | 0.4-0.7 | 服务员分类置信度 |

**调优流程**：
1. 使用默认值部署
2. 手动标注50-100个真实会话
3. 计算每个参数的准确率
4. 调整阈值以最大化F1分数

---

## 应用场景

### 场景1：菜单设计验证（主要）

**假设**：复杂菜单导致点单延迟

**测量方法**：
```
对于每个餐桌会话：
  1. 从视觉系统获取 session_start_time
  2. 从POS系统获取 first_order_time
  3. 计算 order_delay = first_order_time - session_start_time

分析：
  - 所有餐桌的平均 order_delay
  - 分布（50th、90th、95th百分位）
  - 与桌型的相关性（2人桌 vs 4人桌）
```

**行动**：
- 如果 order_delay > 8分钟 → 菜单过于复杂
- 如果 order_delay < 3分钟 → 菜单可能过于简单（品种少）

### 场景2：服务质量监控

**测量方法**：
```
service_responsiveness = first_serving_time - session_start_time
```

**洞察**：
- 首次服务延迟长 → 人手不足或关注度差
- SERVING转换频繁 → 良好的贴心服务
- 零SERVING转换 → 顾客自助（火锅店正常）

### 场景3：翻台率优化

**测量方法**：
```
turnover_time = session_end_time - session_start_time
cleaning_time = CLEANING状态持续时间
```

**洞察**：
- cleaning_time长 → 服务员慢或清理困难
- session_duration短 → 快速翻台（高峰期有利）

### 场景4：容量规划

**测量方法**：
```
对于每个时段（如：下午6-7点）：
  occupied_tables = count(OCCUPIED或SERVING状态的餐桌)
  utilization = occupied_tables / total_tables
```

**洞察**：
- 高峰期利用率低 → 运营问题
- 高利用率 + 长等待时间 → 需要更多餐桌

---

## 未来增强

### 阶段2：顾客行为分析

- 检测顾客环顾（准备点餐）
- 识别"招手"手势呼叫服务员
- 追踪用餐速度（食物消耗率）

### 阶段3：多摄像头追踪

- 追踪顾客旅程：入口 → 餐桌 → 出口
- 测量入口等待时间
- 区分上厕所 vs 提前离开

### 阶段4：预测性警报

- 根据行为预测顾客即将离开
- 提醒服务员准备翻台
- 优化清洁人员分配

---

## 数据输出格式

### 每帧输出

```json
{
  "timestamp": "2025-11-11T18:30:45Z",
  "table_id": "T1",
  "state": "SERVING",
  "customers_present": 4,
  "waiters_present": 1,
  "session_id": "T1_20251111_183000"
}
```

### 会话摘要

```json
{
  "session_id": "T1_20251111_183000",
  "table_id": "T1",
  "start_time": "2025-11-11T18:30:00Z",
  "end_time": "2025-11-11T19:45:30Z",
  "duration_seconds": 4530,
  "customer_count": 4,
  "service_interactions": 8,
  "first_service_delay": 120,
  "order_delay": 180,  // 来自POS系统
  "state_timeline": [
    {"state": "IDLE", "duration": 0},
    {"state": "OCCUPIED", "duration": 3600},
    {"state": "SERVING", "duration": 450},
    {"state": "CLEANING", "duration": 480}
  ]
}
```

---

## 系统要求

### 硬件
- **GPU**：RTX 3060或更好
- **分辨率**：最低1080p（推荐2K）
- **帧率**：15-30 FPS即可（无需实时）

### 软件
- **检测**：YOLOv8m（人员检测）
- **分类**：YOLO11n-cls（服务员/顾客）
- **追踪**：ByteTrack（ID一致性）

### 预期准确率
- **状态检测**：90-95%
- **会话计时**：±30秒
- **误会话率**：<5%

---

## 实施注意事项

1. **ROI标注**：使用交互式多边形工具（参考脚本中包含）
2. **模型选择**：YOLOv8m平衡了速度和准确率，适合餐厅密度
3. **缓冲调优**：从保守开始（较长缓冲），根据误报率调紧
4. **验证**：前两周对照人工日志验证视觉时间戳

---

**文档版本**：1.0
**最后更新**：2025-11-11
**作者**：ASEOfSmartICE团队
