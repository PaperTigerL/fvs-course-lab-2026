# 构建期标签感知加边的参考实现

本目录对应课程实验报告 §5 与 §8.2 的优化设计：在 Vamana 建图完成后，为低频标签的节点补充同标签近邻边，以降低强过滤下 Graph Tunneling 的穿行长度。

> **边界说明**：课程《实验说明》明确“优化部分只要求设计与验证计划，不要求实现”。本目录是**参考实现**，用于把边选择逻辑落成可检查的代码与单元测试；它**没有**接入 GateANN 的 C++ 查询路径，也不替代报告 §5 的 Validation Plan。端到端 Recall 是否提升，必须在 GateANN 上按对照实验重跑后才能下结论。

## 文件

- `label_aware_edges.py`：标签倒排、标签内 kNN、边合并与度上限控制。
- `test_label_aware_edges.py`：五个性质测试（同标签、无自环、无重复、度上限、未见标签不受影响）。
- `README.md`：本文件。

## 算法

1. 从 `labels[i]`（第 i 个节点的标签集合）构建 `label -> [node_id]` 倒排，并统计频率。
2. 对频率低于阈值的标签，取该标签下的节点向量，计算标签内 kNN，得到候选同标签边。
3. 将候选边与原始邻接表合并：原始边优先保留；新增边按距离升序加入；去掉自环与重复边；每个节点的度不超过 `degree_cap`。
4. 查询期把新增边并入 `FullAdjIndex`（或从旁路文件加载）；Pre-I/O Filtering 与距离计算逻辑不变，Tunneling 沿增强后的邻接表遍历。

## 运行

```bash
python optimization/test_label_aware_edges.py
python optimization/label_aware_edges.py
```

参考实现只依赖 NumPy。生产实现应把标签内 kNN 换成 ANN（例如复用现有图或 PQ 码本），避免低频标签节点数较大时退化为 O(n²)。

## 验证计划（与报告 §5 一致）

- 对照组：当前 GateANN（不启用 label-aware 边增强），3 轮。
- 自变量：是否启用边增强（on/off）。
- 控制变量：L=320、threads=1、beamwidth=8、K=10、FullAdj R=32、同样的 200 条查询、同一机器与数据集。
- 指标：Low / Medium / High 的 Recall@10、Mean Latency、Mean I/O、FilterSkips、Tunnel time。
- 可证伪预期：Low bucket、L=320 的 Recall 从 34.3% 提升到 85% 以上，且 I/O 增幅小于 1.5 倍；若 Recall 仍低于 50% 或 I/O 增幅超过 3 倍，则否定该优化方向。
