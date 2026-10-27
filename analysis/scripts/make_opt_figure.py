# -*- coding: utf-8 -*-
"""Figure 6: low-selectivity prefilter Pareto and Low-bucket L scan."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path

plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams.update({"font.size": 8.5, "axes.titlesize": 9.5, "axes.labelsize": 8.5,
                     "legend.fontsize": 7.5, "figure.dpi": 200})

csv = Path("analysis/data/optimization_prefilter_results.csv")
df = pd.read_csv(csv)
out = Path("analysis/figures/fig6_prefilter.png")
out.parent.mkdir(parents=True, exist_ok=True)

def med(sub, key):
    return float(np.median(sub[key].astype(float)))

low = df[(df.bucket == "low") & (df.L == 320)]
base = low[low.variant == "baseline"]
pvals = [8, 16, 32, 64, 128]
pref = {p: low[(low.variant == "prefilter") & (low.P == p)] for p in pvals}

fig, axes = plt.subplots(1, 2, figsize=(6.3, 3.2), gridspec_kw={"width_ratios": [1.25, 1]})
ax = axes[0]
ax.axhline(85, color="#999999", linestyle="--", linewidth=0.9)
ax.text(3.45, 86, "85%", fontsize=7, color="#666666", ha="right")
ax.scatter([med(base, "mean_latency_us") / 1000], [med(base, "recall_percent")],
           marker="*", s=110, color="#555555", zorder=3, label="基线 (tunneling)")
ax.annotate("基线\n34.3%", (med(base, "mean_latency_us") / 1000, med(base, "recall_percent")),
            textcoords="offset points", xytext=(6, -12), fontsize=7, color="#555555")
for p in pvals:
    x = med(pref[p], "mean_latency_us") / 1000
    y = med(pref[p], "recall_percent")
    ax.scatter([x], [y], s=28, color="#1f77b4", zorder=3)
    offsets = {8: (8, -16), 16: (8, -18), 32: (8, -20)}
    if p in offsets:
        ax.annotate(f"P={p}\n{y:.1f}%", (x, y), textcoords="offset points",
                    xytext=offsets[p], fontsize=6.7, color="#1f4e79",
                    ha="left")
ax.plot([med(pref[p], "mean_latency_us") / 1000 for p in pvals],
        [med(pref[p], "recall_percent") for p in pvals],
        color="#1f77b4", linewidth=1.3, alpha=0.8)
ax.text(2.0, 76, "P=64：99.6% / 1.69 ms\nP=128：100.0% / 3.45 ms",
        fontsize=6.5, color="#1f4e79", va="top")
ax.set_xlabel("平均查询延迟（ms）")
ax.set_ylabel("Recall@10（%）")
ax.set_title("Low L=320：P 与 Recall–延迟权衡")
ax.set_xlim(0.35, 3.65)
ax.set_ylim(25, 103)
ax.grid(True, alpha=0.3)

ax = axes[1]
bl = df[(df.bucket == "low") & (df.variant == "baseline") & (df.L.isin([160, 320, 640]))]
pr = df[(df.bucket == "low") & (df.variant == "prefilter") & (df.P == 32) & (df.L.isin([160, 320, 640]))]
Ls = [160, 320, 640]
b_rec = [med(bl[bl.L == L], "recall_percent") for L in Ls]
b_lat = [med(bl[bl.L == L], "mean_latency_us") / 1000 for L in Ls]
p_rec = [med(pr[pr.L == L], "recall_percent") for L in Ls]
p_lat = [med(pr[pr.L == L], "mean_latency_us") / 1000 for L in Ls]
ax.plot(Ls, b_rec, marker="o", color="#555555", linewidth=1.5, markersize=5, label="基线")
ax.plot(Ls, p_rec, marker="s", color="#1f77b4", linewidth=1.5, markersize=5, label="prefilter P=32")
for L, r, lat in zip(Ls, b_rec, b_lat):
    ax.annotate(f"{r:.1f}%\n{lat:.2f}ms", (L, r), textcoords="offset points", xytext=(0, -20),
                fontsize=6.5, color="#555555", ha="center")
for L, r, lat in zip(Ls, p_rec, p_lat):
    ax.annotate(f"{r:.1f}%\n{lat:.2f}ms", (L, r), textcoords="offset points", xytext=(0, -38),
                fontsize=6.5, color="#1f4e79", ha="center")
ax.text(400, 62, "基线", fontsize=7.5, color="#555555")
ax.text(400, 88, "prefilter P=32", fontsize=7.5, color="#1f77b4")
ax.set_xticks(Ls)
ax.set_xlabel("搜索预算 L")
ax.set_ylabel("Recall@10（%）")
ax.set_title("Low bucket：L 扫描（P=32）")
ax.set_ylim(0, 105)
ax.grid(True, alpha=0.3)

fig.text(0.01, 0.005, "注：3 轮中位数；P 为读取的 PQ top-P 候选数；基线为原 GateANN tunneling。",
         fontsize=6.5, color="#666666")
plt.tight_layout(rect=(0, 0.04, 1, 1))
plt.savefig(out, dpi=300, bbox_inches="tight")
print("saved", out)
