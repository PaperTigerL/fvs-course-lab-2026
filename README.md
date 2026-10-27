# FVS Course Lab 2026：SSD 驻留过滤向量检索

华中科技大学《计算机系统设计》课程实验的复现代码与数据。实验比较两套 SSD 驻留过滤向量检索系统：

- **PipeANN-Filter**：在 PipeANN 的异步 I/O 流水线上做 Pre / In / Post 三条过滤路径的查询期路由；
- **GateANN**：Pre-I/O Filtering + Graph Tunneling，用内存标签集与全邻居表减少无效 SSD 读。

最终实验报告单独提交；本仓库只保留可公开的代码、聚合数据、图表与优化实现，不包含数据集、预构建索引、原始运行目录与个人信息。

## 关键结果

YFCC Course Dataset v1（1M × 192D uint8，L2，单线程，beamwidth=8，K=10，3 轮中位数）：

| 场景 | 系统/配置 | Recall@10 | 平均延迟 | 逻辑 I/O/查询 |
|---|---|---:|---:|---:|
| High（selectivity 12.323%） | PipeANN-Filter（L=40） | 92.8% | 3.49 ms | 142 |
| High（selectivity 12.323%） | GateANN（L=320） | 93.2% | 1.66 ms | 46.7 |
| Low（selectivity 0.545%） | PipeANN-Filter（L=40） | 98.6% | 1.17 ms | 80.0 |
| Low（selectivity 0.545%） | GateANN 基线（L=320） | 34.3% | 0.766 ms | 4.38 |
| Low（selectivity 0.545%） | **GateANN + prefilter P=16** | **87.15%** | **0.673 ms** | **16** |
| Low（selectivity 0.545%） | **GateANN + prefilter P=32** | **96.50%** | **0.993 ms** | **32** |

资源：PipeANN-Filter 索引 8.43 GiB、查询峰值 RSS 157 MiB；GateANN 基线索引 0.47 GiB、查询峰值 RSS 428 MiB；prefilter 版查询峰值 RSS 约 490 MiB（+约 62 MiB 倒排索引与查询缓冲）。

优化不是“继续给图加边”。我们实测了两次加边：同标签边把 Low L=320 从 34.30% 只改到 34.35%，因为合格子图内部加密不能解决“搜索到不了第一个合格节点”；Low 标签桥边把 Recall 提到 73.75%，但 I/O 涨到 354、延迟约 9.2 ms。最终实现改为**低选择率 prefilter**：内存倒排标签索引枚举合格节点，PQ 粗排后只读 top-P，再精确重排。P=16/32 的结果如上；Medium/High 不触发 prefilter，保持 72.05%/93.20% 不变。

## 目录

```
adapters/   课程提供的统一适配器（调用两套系统原始二进制）
scripts/    环境准备、数据/索引下载校验、正式/补充实验、结果聚合
config/     课程固定参数（threads/beamwidth/K/L 等）
patches/    GateANN AIO 兼容补丁 + 低选择率 prefilter 优化补丁
analysis/
  data/     results_main.csv（30 行）、supp 3 轮聚合、optimization_prefilter_results.csv、environment.txt
  figures/  5 张结果图 + 3 张机制示意图 + fig6_prefilter.png
  scripts/  analyze.py、make_result_figures.py、make_exp_figures.py、make_opt_figure.py
optimization/
  build_label_edges.py      同标签边生成（失败尝试，保留证据）
  build_label_bridges.py    Low 标签桥边生成（失败尝试，保留证据）
  run_prefilter.py          基线 vs prefilter 3 轮对照矩阵
  run_labelaware.py         加边探索的运行脚本
  label_aware_edges.py      初版边选择参考实现 + 单测
```

## 环境

- Windows 11 + WSL2 Ubuntu 24.04.1（内核 5.15.167.4-microsoft-standard-WSL2）
- Intel i7-10750H / 16 GB / NVMe SSD（WSL2 VHDX，ext4）
- GCC 13.3.0、CMake、Linux AIO、Python 3.12 + NumPy + FAISS CPU
- PipeANN commit `2ec84fe20c37dc3cc236b66f7eba31c0cc80bf1e`
- GateANN commit `71e87cbf0e25c0400c0109dd25a64a7c4dccc9dd` + AIO 补丁 + prefilter 补丁
- 正式实验 ID：`20260915-154720`；优化对照：`prefilter_matrix`

WSL2 的绝对延迟/QPS 不代表原生 NVMe；所有跨系统比较都在同一虚拟环境中完成。

## 复现

本仓库不包含 `systems/`、`datasets/`、`course_runs/`（体积与课程约定原因）。先按课程仓库获取两套系统源码、数据集与预构建索引：

- 课程仓库：`https://gitee.com/wei-fangyu/fvs-course-lab`
- 按 `docs/系统准备.md` 编译 PipeANN / GateANN，并从课程页面下载 `datasets/yfcc_course_v1` 与 `course_runs/indices`

基础实验：

```bash
bash scripts/prepare_pipeann.sh
bash scripts/prepare_gateann.sh
bash scripts/download_dataset.sh
bash scripts/run_debug_validation.sh          # 两系统均需 PASS
bash scripts/download_indexes.sh
bash scripts/check_indexes.sh
bash scripts/run_formal_experiments.sh        # 3 轮 × 10 配置
REPEATS=3 L_LIST="320 640 1280 2560" bash scripts/run_supp_low_L.sh
python3 analysis/scripts/make_result_figures.py
```

优化实现：

```bash
cd systems/GateANN-public
git apply ../../patches/gateann_labelaware_prefilter.patch
cmake --build build -j 8

# 基线：补丁前二进制（备份为 search_disk_index_yfcc.orig）
# 优化：补丁后二进制 + 环境变量
GATEANN_PREFILTER_P=16 GATEANN_PREFILTER_MAX_LABEL=12000 \
  python3 adapters/gateann_adapter.py search \
  --repo systems/GateANN-public --dataset-root datasets/yfcc_course_v1 \
  --tier formal --bucket low --L 320 --run-id opt-low-P16

# 或直接跑完整对照矩阵（需要课程环境的数据/索引路径）
python3 optimization/run_prefilter.py
```

补丁只改 4 个文件：`include/utils/spmat_filter_store.h`（标签倒排）、`include/ssd_index.h`（`prefilter_search` 声明）、`src/search/pipe_search.cpp`（PQ 粗排 + top-P 读 + 精确重排）、`tests/search_disk_index_yfcc.cpp`（按标签规模选择路径）。`GATEANN_PREFILTER_MAX_LABEL` 默认 12000；本数据 Low 标签 2,499–8,513 个节点会触发，Medium（17,652+）与 High（70,738+）继续走 tunneling。

`gateann_aio_compat.patch` 的 SHA256 会写入 `environment.txt`，便于复核。

## 优化探索记录

`optimization/` 里的加边脚本是**失败尝试的可复现记录**，不是最终方案：

- 同标签边（15 标签，k=8）：Low L=320 34.35%，与基线 34.30% 基本一致；
- Low 标签桥边（每节点最多 16 条）：73.75%，但 354 I/O、约 9.2 ms；
- 低选择率 prefilter（最终）：P=16 87.15% / 0.673 ms / 16 I/O；P=32 96.50% / 0.993 ms / 32 I/O。

这些脚本需要课程数据与 GateANN 源码；`label_aware_edges.py` 的 6 个单测可在无数据情况下运行：

```bash
python optimization/test_label_aware_edges.py
python optimization/label_aware_edges.py
```

## 归因

`adapters/`、`scripts/`、`config/`、`patches/gateann_aio_compat.patch` 与课程模板来自课程仓库，版权归课程作者；本仓库的聚合数据、图表、分析脚本、prefilter 实现与加边探索代码由本人完成，仅用于课程学习与复现。数据集与预构建索引不随仓库分发，请从课程页面获取。
