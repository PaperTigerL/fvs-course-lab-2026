# GateANN 低选择率 prefilter 实现

本目录是课程实验 §5 优化的完整实现与探索记录。最终方案不是“构建期加边”，而是**选择率感知的低选择率 prefilter**：内存标签倒排 → PQ 粗排 → top-P 读 SSD → 精确重排。

> 结果（Low L=320，YFCC 1M，3 轮中位数）：基线 34.30% / 0.766 ms / 4.38 I/O；prefilter P=16 **87.15% / 0.673 ms / 16 I/O**；P=32 **96.50% / 0.993 ms / 32 I/O**。Medium/High 不触发 prefilter，保持 72.05%/93.20%。

## 文件

| 文件 | 作用 |
|---|---|
| `../patches/gateann_labelaware_prefilter.patch` | 最终 C++ 实现：`SpmatFilterStore` 倒排、`SSDIndex::prefilter_search`、按标签规模选择路径 |
| `build_label_edges.py` | 同标签边生成（失败尝试：34.35%，保留作证据） |
| `build_label_bridges.py` | Low 标签桥边生成（失败尝试：73.75% 但 354 I/O） |
| `run_prefilter.py` | 基线 vs prefilter 的 3 轮对照矩阵，输出 `analysis/data/optimization_prefilter_results.csv` |
| `run_labelaware.py` | 加边探索的运行脚本（可选） |
| `label_aware_edges.py` | 初版同标签边选择参考实现 |
| `test_label_aware_edges.py` | 6 个性质测试（同标签、无自环、无重复、度上限、未见标签、最小频率） |

## 最终实现

补丁修改四个文件：

1. `include/utils/spmat_filter_store.h`：加载 CSR 标签时构建 `label -> node_ids` 倒排；
2. `include/ssd_index.h`：声明 `prefilter_search` 与 `label_node_count`；
3. `src/search/pipe_search.cpp`：枚举标签节点，按 1024 一组算 PQ 距离，保留 top-P；每 32 个候选一批读节点页，精确 L2 重排；
4. `tests/search_disk_index_yfcc.cpp`：单标签且 `label_node_count <= GATEANN_PREFILTER_MAX_LABEL` 时走 prefilter，否则走原 tunneling。

环境变量：

- `GATEANN_PREFILTER_P`：读取的 top-P 候选数，默认 128；推荐 16（低延迟）或 32（高召回）。
- `GATEANN_PREFILTER_MAX_LABEL`：启用 prefilter 的标签规模上限，默认 12000；本数据 Low 标签 2,499–8,513 会触发，Medium/High 不触发。

应用：

```bash
cd systems/GateANN-public
git apply ../../patches/gateann_labelaware_prefilter.patch
cmake --build build -j 8

GATEANN_PREFILTER_P=16 GATEANN_PREFILTER_MAX_LABEL=12000 \
  python3 adapters/gateann_adapter.py search \
  --repo systems/GateANN-public --dataset-root datasets/yfcc_course_v1 \
  --tier formal --bucket low --L 320 --run-id opt-low-P16
```

## 加边探索（为什么被否定）

同标签边：对 15 个工作负载标签用 HNSW 做标签内 k=8 kNN，合并进 `FullAdjIndex`，额外边上限 12。Low L=320 实测 34.35%，与基线 34.30% 基本一致——同标签边只加密合格子图，搜索到不了第一个合格节点时无效。

Low 标签桥边：给每个节点连到最近的 4 个 Low 标签节点，每节点最多 16 条额外边，并让 Filter-Pass 邻居优先进入候选池。Recall 升到 73.75%，但 Mean I/O 354、QPS 109；桥边与查询无关，读入大量远距离合格节点。该负结果直接促成了 prefilter 的设计。

生成脚本：

```bash
python optimization/build_label_edges.py \
  --base-u8bin datasets/yfcc_course_v1/formal_1000000/base.u8bin \
  --base-spmat datasets/yfcc_course_v1/formal_1000000/base.metadata.spmat \
  --workload-root datasets/yfcc_course_v1/formal_1000000/workloads \
  --out course_runs/indices/gateann/formal_1000000/yfcc.labelaware.R12

python optimization/build_label_bridges.py \
  --base-u8bin datasets/yfcc_course_v1/formal_1000000/base.u8bin \
  --base-spmat datasets/yfcc_course_v1/formal_1000000/base.metadata.spmat \
  --labels 4780,600,747,113,42 \
  --out course_runs/indices/gateann/formal_1000000/yfcc.bridge.low.R16
```

加边文件通过 `GATEANN_EXTRA_EDGES` 加载（可选代码），最终 prefilter 不需要它。

## 单测

```bash
python optimization/test_label_aware_edges.py
python optimization/label_aware_edges.py
```

单测只验证初版边选择逻辑（同标签、无自环/重复、度上限、未见标签、最小频率），不能替代端到端实验。
