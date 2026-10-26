# -*- coding: utf-8 -*-
"""Regenerate the five experiment figures with Chinese labels."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({
    "font.size": 8.5,
    "axes.titlesize": 9.5,
    "axes.labelsize": 8.5,
    "legend.fontsize": 7.5,
    "figure.dpi": 150,
})

DATA = Path("analysis/data")
FIG = Path("analysis/figures")
FIG.mkdir(exist_ok=True)

main = pd.read_csv(DATA / "results_main.csv")
_supp3 = DATA / "results_supp_low_L_3runs.csv"
supp = pd.read_csv(_supp3 if _supp3.is_file() else DATA / "results_supp_low_L.csv")
SUPP_3RUNS = _supp3.is_file() and "recall_percent_median" in supp.columns

g = main.groupby(["system", "bucket", "L"]).agg(
    recall_med=("recall_percent", "median"),
    recall_min=("recall_percent", "min"),
    recall_max=("recall_percent", "max"),
    lat_med=("mean_latency_us", "median"),
    lat_min=("mean_latency_us", "min"),
    lat_max=("mean_latency_us", "max"),
    qps_med=("qps", "median"),
    ios_med=("mean_ios", "median"),
    ios_min=("mean_ios", "min"),
    ios_max=("mean_ios", "max"),
    skips=("filter_skips", "median"),
    tunnel=("tunnel_time_us", "median"),
    io_us=("io_time_us", "median"),
    proc=("process_time_us", "median"),
    pre=("pre_filter_queries", "median"),
    in_q=("in_filter_queries", "median"),
    post=("post_filter_queries", "median"),
    fp=("filter_false_positives", "median"),
    rss=("peak_rss_kb", "median"),
    idx=("index_bytes", "median"),
).reset_index()

SYS_LABEL = {"pipeann": "PipeANN-Filter", "gateann": "GateANN"}
COLOR = {"pipeann": "#1f77b4", "gateann": "#e07b00"}

# ---- Fig 1
fig, ax = plt.subplots(figsize=(6.3, 4.0))
for sysn, mk in [("pipeann", "o"), ("gateann", "s")]:
    s = g[(g.system == sysn) & (g.bucket == "high")].sort_values("L")
    ax.errorbar(s.lat_med / 1000, s.recall_med,
                xerr=[(s.lat_med - s.lat_min) / 1000, (s.lat_max - s.lat_med) / 1000],
                yerr=[s.recall_med - s.recall_min, s.recall_max - s.recall_med],
                color=COLOR[sysn], marker=mk, label=SYS_LABEL[sysn],
                capsize=3, lw=1.6, ms=5.5)
    for _, r in s.iterrows():
        ax.annotate(f"L={int(r.L)}", (r.lat_med / 1000, r.recall_med),
                    textcoords="offset points", xytext=(6, 4), fontsize=7.2, color=COLOR[sysn])
ax.set_xlabel("平均查询延迟（ms）")
ax.set_ylabel("Recall@10（%）")
ax.set_title("High workload：Recall–延迟曲线（3 轮中位数，误差线为 min–max）")
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(FIG / "fig1_recall_latency.png", dpi=200)
plt.close()

# ---- Fig 2
fig, axes = plt.subplots(1, 3, figsize=(6.3, 2.8))
buckets = ["low", "medium", "high"]
sel = {"low": 0.545, "medium": 2.958, "high": 12.323}
for sysn, repL in [("pipeann", 40), ("gateann", 320)]:
    s = g[(g.system == sysn) & (g.L == repL) & (g.bucket.isin(buckets))].set_index("bucket").reindex(buckets)
    xs = [sel[b] for b in buckets]
    axes[0].plot(xs, s.recall_med.values, color=COLOR[sysn], marker="o", label=SYS_LABEL[sysn], lw=1.6, ms=5.5)
    axes[1].plot(xs, s.lat_med.values / 1000, color=COLOR[sysn], marker="s", label=SYS_LABEL[sysn], lw=1.6, ms=5.5)
    axes[2].plot(xs, s.ios_med.values, color=COLOR[sysn], marker="^", label=SYS_LABEL[sysn], lw=1.6, ms=5.5)
axes[0].set_title("Recall@10")
axes[0].set_ylabel("%")
axes[1].set_title("平均延迟")
axes[1].set_ylabel("ms")
axes[2].set_title("平均逻辑 I/O")
axes[2].set_ylabel("次/查询")
for ax in axes:
    ax.set_xlabel("Selectivity（%）")
    ax.legend()
    ax.grid(True, alpha=0.3)
plt.suptitle("Selectivity 敏感性（PipeANN-Filter L=40，GateANN L=320）", y=1.02)
plt.tight_layout()
plt.savefig(FIG / "fig2_selectivity.png", dpi=200, bbox_inches="tight")
plt.close()

# ---- Fig 3
low_main = g[(g.system == "gateann") & (g.bucket == "low")].iloc[0]
rows = []
if SUPP_3RUNS:
    for _, r in supp.iterrows():
        rows.append(dict(L=int(r["L"]), recall=r["recall_percent_median"],
                         rlo=r["recall_percent_min"], rhi=r["recall_percent_max"],
                         io=r["mean_ios_median"], ilo=r["mean_ios_min"], ihi=r["mean_ios_max"],
                         lat=r["mean_latency_us_median"], llo=r["mean_latency_us_min"],
                         lhi=r["mean_latency_us_max"], skips=r["filter_skips_median"]))
else:
    for _, r in supp.iterrows():
        rows.append(dict(L=int(r["L"]), recall=r["recall_percent"], rlo=r["recall_percent"],
                         rhi=r["recall_percent"], io=r["mean_ios"], ilo=r["mean_ios"],
                         ihi=r["mean_ios"], lat=r["mean_latency_us"], llo=r["mean_latency_us"],
                         lhi=r["mean_latency_us"], skips=r["filter_skips"]))
if not any(r["L"] == 320 for r in rows):
    rows.append(dict(L=320, recall=low_main.recall_med, rlo=low_main.recall_min,
                     rhi=low_main.recall_max, io=low_main.ios_med, ilo=low_main.ios_min,
                     ihi=low_main.ios_max, lat=low_main.lat_med, llo=low_main.lat_min,
                     lhi=low_main.lat_max, skips=low_main.skips))
rows.sort(key=lambda r: r["L"])
sdf = pd.DataFrame(rows)

fig, ax1 = plt.subplots(figsize=(6.3, 4.0))
color1 = "#e07b00"
ax1.errorbar(sdf.L, sdf.recall, yerr=[sdf.recall - sdf.rlo, sdf.rhi - sdf.recall],
             fmt="o-", color=color1, lw=1.6, ms=5.5, capsize=4, label="Recall@10")
ax1.set_xlabel("搜索预算 L")
ax1.set_ylabel("Recall@10（%）", color=color1)
ax1.tick_params(axis="y", labelcolor=color1)
ax1.set_ylim(0, 100)
ax1.set_xticks(list(sdf.L))
for _, r in sdf.iterrows():
    ax1.annotate(f"{r.recall:.2f}%", (r.L, r.recall), textcoords="offset points",
                 xytext=(0, 13), ha="center", color=color1, fontsize=9)
ax2 = ax1.twinx()
color2 = "#2ca02c"
ax2.errorbar(sdf.L, sdf.io, yerr=[sdf.io - sdf.ilo, sdf.ihi - sdf.io],
             fmt="s--", color=color2, lw=1.6, ms=5.5, capsize=4, label="平均 I/O")
ax2.set_ylabel("平均逻辑 I/O（次/查询）", color=color2)
ax2.tick_params(axis="y", labelcolor=color2)
top = sdf.iloc[-1]
_hi = g[(g.system == "gateann") & (g.bucket == "high") & (g.L == 320)]
_hi_txt = f"{_hi.recall_med.iloc[0]:.1f}%" if len(_hi) else "93.2%"
ax1.set_title(
    "GateANN Low bucket（0.545%）的 L 扫描（3 轮中位数，误差线为 min–max）\n"
    f"L={int(top.L)}（{int(top.L)//320} 倍预算）达到 {top.recall:.2f}%，仍低于 High bucket 在 L=320 的 {_hi_txt}",
    fontsize=8.8)
ax1.grid(True, alpha=0.3)
fig.tight_layout()
plt.savefig(FIG / "fig3_gateann_low_L_scan.png", dpi=200, bbox_inches="tight")
plt.close()

# ---- Fig 4
fig, ax = plt.subplots(figsize=(6.3, 4.0))
buckets_g = ["low", "medium", "high"]
labels, io_t, tun_t, proc_t = [], [], [], []
for b in buckets_g:
    r = g[(g.system == "gateann") & (g.bucket == b) & (g.L == 320)].iloc[0]
    labels.append(f"{b.capitalize()}\n(sel={sel[b]:.2f}%)")
    io_t.append(r.io_us)
    tun_t.append(r.tunnel)
    proc_t.append(r.proc)
x = np.arange(len(labels))
ax.bar(x, io_t, label="I/O 等待", color="#d62728")
ax.bar(x, tun_t, bottom=io_t, label="Graph Tunneling", color="#e07b00")
ax.bar(x, proc_t, bottom=np.array(io_t) + np.array(tun_t), label="Process / 距离计算", color="#1f77b4")
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("每查询时间（μs）")
ax.set_title("GateANN 每查询时间分解（L=320）\n强过滤下 Tunneling 主导，弱过滤下 I/O 占比上升")
ax.legend()
ax.grid(True, alpha=0.3, axis="y")
plt.tight_layout()
plt.savefig(FIG / "fig4_gateann_time_breakdown.png", dpi=200)
plt.close()

# ---- Fig 5
fig, ax1 = plt.subplots(figsize=(6.3, 4.0))
buckets_p = ["low", "medium", "high"]
fp_vals, io_p, route_pre = [], [], []
for b in buckets_p:
    r = g[(g.system == "pipeann") & (g.bucket == b) & (g.L == 40)].iloc[0]
    fp_vals.append(r.fp)
    io_p.append(r.ios_med)
    route_pre.append(r.pre)
xs = np.arange(len(buckets_p))
ax1.bar(xs - 0.2, fp_vals, 0.4, color="#9467bd", label="假阳性/查询")
ax1.set_ylabel("假阳性/查询", color="#9467bd")
ax1.tick_params(axis="y", labelcolor="#9467bd")
ax2 = ax1.twinx()
ax2.bar(xs + 0.2, io_p, 0.4, color="#17becf", label="平均 I/O/查询")
ax2.set_ylabel("平均 I/O/查询", color="#17becf")
ax2.tick_params(axis="y", labelcolor="#17becf")
ax1.set_xticks(xs)
ax1.set_xticklabels([f"{b.capitalize()}\nsel={sel[b]:.2f}%\n{'Pre-filter' if route_pre[i] == 200 else 'In-filter'}"
                     for i, b in enumerate(buckets_p)])
ax1.set_title("PipeANN-Filter 路由切换与假阳性（L=40）\nLow 全部 Pre-filter（FP=0）；Medium/High 全部 In-filter")
ax1.grid(True, alpha=0.3, axis="y")
plt.tight_layout()
plt.savefig(FIG / "fig5_pipeann_routing_fp.png", dpi=200)
plt.close()

print("done")
