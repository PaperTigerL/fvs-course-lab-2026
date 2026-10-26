# FVS Course Lab 2026：SSD 驻留过滤向量检索

华中科技大学《计算机系统设计》课程实验的复现材料。实验比较两套 SSD 驻留过滤向量检索系统：

- **PipeANN-Filter**：在 PipeANN 的异步 I/O 流水线上做 Pre / In / Post 三条过滤路径的查询期路由；
- **GateANN**：Pre-I/O Filtering + Graph Tunneling，用内存标签集与全邻居表减少无效 SSD 读。

最终实验报告单独提交；本仓库只保留可公开的代码、聚合数据、图表与优化参考实现，不包含数据集、预构建索引、原始运行目录与个人信息。

## 关键结果

YFCC Course Dataset v1（1M × 192D uint8，L2，单线程，beamwidth=8，K=10，3 轮中位数）：

| 场景 | 系统 | Recall@10 | 平均延迟 | 逻辑 I/O/查询 |
|---|---|---:|---:|---:|
| High（selectivity 12.323%） | PipeANN-Filter（L=40） | 92.8% | 3.49 ms | 142 |
| High（selectivity 12.323%） | GateANN（L=320） | 93.2% | 1.66 ms | 46.7 |
| Low（selectivity 0.545%） | PipeANN-Filter（L=40） | 98.6% | 1.17 ms | 80.0 |
| Low（selectivity 0.545%） | GateANN（L=320） | 34.3% | 0.77 ms | 4.38 |

资源：PipeANN-Filter 索引 8.43 GiB、查询峰值 RSS 157 MiB；GateANN 索引 0.47 GiB、查询峰值 RSS 427 MiB。

补充实验（GateANN Low bucket，3 轮）：L 从 320 增至 2560（8 倍预算）时 Recall 从 34.3% 升到 83.75%，仍低于 High bucket 同预算的 93.2%；主导瓶颈是合格节点在 label-blind 图上稀疏导致的穿行路径过长，而非单纯预算不足。

## 目录

```
adapters/   课程提供的统一适配器（调用两套系统原始二进制）
scripts/    环境准备、数据/索引下载校验、正式/补充实验、结果聚合
config/     课程固定参数（threads/beamwidth/K/L 等）
patches/    GateANN AIO 兼容补丁（cb.data -> cb[j].data）
analysis/
  data/     results_main.csv（30 行）、supp 3 轮聚合、environment.txt
  figures/  5 张结果图 + 3 张机制示意图
  scripts/  analyze.py、make_result_figures.py、make_exp_figures.py
optimization/  构建期标签感知加边的参考实现与单元测试
```

## 环境

- Windows 11 + WSL2 Ubuntu 24.04.1（内核 5.15.167.4-microsoft-standard-WSL2）
- Intel i7-10750H / 16 GB / NVMe SSD（WSL2 VHDX，ext4）
- GCC 13.3.0、CMake、Linux AIO
- PipeANN commit `2ec84fe20c37dc3cc236b66f7eba31c0cc80bf1e`
- GateANN commit `71e87cbf0e25c0400c0109dd25a64a7c4dccc9dd` + 一行 AIO 补丁
- 正式实验 ID：`20260915-154720`

WSL2 的绝对延迟/QPS 不代表原生 NVMe；所有跨系统比较都在同一虚拟环境中完成。

## 复现

本仓库不包含 `systems/`、`datasets/`、`course_runs/`（体积与课程约定原因）。先按课程仓库获取两套系统源码、数据集与预构建索引：

- 课程仓库：`https://gitee.com/wei-fangyu/fvs-course-lab`
- 按 `docs/系统准备.md` 编译 PipeANN / GateANN，并从课程页面下载 `datasets/yfcc_course_v1` 与 `course_runs/indices`

然后：

```bash
bash scripts/prepare_pipeann.sh
bash scripts/prepare_gateann.sh
bash scripts/download_dataset.sh
bash scripts/run_debug_validation.sh          # 两系统均需 PASS
bash scripts/download_indexes.sh
bash scripts/check_indexes.sh
bash scripts/run_formal_experiments.sh        # 3 轮 × 10 配置
REPEATS=3 L_LIST="320 640 1280 2560" bash scripts/run_supp_low_L.sh
python3 analysis/scripts/analyze.py           # 或 make_result_figures.py
```

`gateann_aio_compat.patch` 的 SHA256 会写入 `environment.txt`，便于复核。

## 优化参考实现

`optimization/` 实现“构建期为低频标签补充同标签近邻边”的边选择逻辑，并提供 6 个性质测试：

```bash
python optimization/test_label_aware_edges.py
python optimization/label_aware_edges.py
```

它**没有**接入 GateANN 的 C++ 查询路径；课程要求优化部分只需设计与验证计划。端到端效果需按报告 §5 的 Validation Plan 在 GateANN 上重跑（Low bucket、L=320，预期 Recall ≥ 85%、I/O 增幅 < 1.5×；若 Recall < 50% 或 I/O 增幅 > 3× 则否定该方向）。

## 归因

`adapters/`、`scripts/`、`config/`、`patches/` 与课程模板来自课程仓库，版权归课程作者；本仓库的聚合数据、图表、分析脚本与优化参考实现由本人完成，仅用于课程学习与复现。数据集与预构建索引不随仓库分发，请从课程页面获取。
