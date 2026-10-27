# 实验数据分析

## 数据文件

- `data/results_main.csv`：正式实验 30 行（2 系统 × 5 配置 × 3 轮）。
- `data/results_supp_low_L_3runs.csv`：GateANN Low bucket L 扫描的 3 轮聚合（median/min/max × L=320/640/1280/2560）。
- `data/results_supp_low_L.csv`：初版单轮，保留作历史记录。
- `data/environment.txt`：正式实验的环境、commit、补丁 SHA256、CPU/内存/块设备信息。
- `data/optimization_prefilter_results.csv`：基线 vs prefilter 对照（Low L=320 的 P∈{8,16,32,64,128} 各 3 轮、Low L=160/640、Medium/High L=320）。
- `data/labelaware_R12.json`、`data/bridge_low_R16.json`：两次加边探索的生成参数与统计（失败记录）。

字段说明见课程仓库 `docs/结果分析指南.md`。核心字段：`recall_percent`、`mean_latency_us`、`mean_ios`、`qps`、`peak_rss_kb`、`index_bytes`、`pre_filter_queries`、`in_filter_queries`、`post_filter_queries`、`filter_false_positives`、`filter_skips`、`io_time_us`、`tunnel_time_us`、`process_time_us`。

## 图表

```bash
python analysis/scripts/analyze.py             # 课程原始绘图脚本（英文标签）
python analysis/scripts/make_result_figures.py # 中文标签版本（报告使用）
python analysis/scripts/make_exp_figures.py    # 平台与两系统机制示意图
python analysis/scripts/make_opt_figure.py     # 图 6：prefilter P 扫描与 L 扫描
```

`make_result_figures.py` 从 `analysis/data` 读取 CSV，输出到 `analysis/figures`；`make_exp_figures.py` 输出 3 张示意图；`make_opt_figure.py` 读取 `optimization_prefilter_results.csv`，输出 `fig6_prefilter.png`。图中所有误差线均为 3 轮 min–max，中心值为 3 轮中位数。

## 口径提醒

- `mean_ios` 是各系统 Query Phase 的逻辑 I/O，不等于块设备物理 I/O；PipeANN-Filter 的 `IO size` 为 8192 B，GateANN 的 `Size per IO` 为 4096 B。
- `elapsed_seconds` 含索引加载与初始化，不作为查询延迟；报告统一使用 `mean_latency_us`。
- 补充实验在同一进程内按 L 从小到大连续执行，延迟绝对值高于正式实验；只用于观察 L 之间的相对趋势。
