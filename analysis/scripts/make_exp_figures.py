# -*- coding: utf-8 -*-
"""Print-sized diagrams for the experiment report."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import os

plt.rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["savefig.facecolor"] = "white"

OUT = "analysis/figures"
os.makedirs(OUT, exist_ok=True)

BLUE = "#2F5597"; BLUE_L = "#DCE6F2"
GREEN = "#2E7D5B"; GREEN_L = "#DCEFE6"
ORANGE = "#B45F06"; ORANGE_L = "#FCE8D5"
RED = "#B02418"
GRAY = "#4D4D4D"; GRAY_L = "#EFEFEF"
PURPLE = "#5B3F8C"; PURPLE_L = "#E8E1F3"


def box(ax, x, y, w, h, text, fc, ec, fs=7.5, bold=False, tc="#222222", lw=0.9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.6",
                                linewidth=lw, edgecolor=ec, facecolor=fc))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=tc, fontweight="bold" if bold else "normal", linespacing=1.35)


def arrow(ax, x1, y1, x2, y2, color=GRAY, lw=1.0, rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=8,
                                 linewidth=lw, color=color,
                                 connectionstyle="arc3,rad=%s" % rad))


# ---------------- Fig 1-1 platform
fig, ax = plt.subplots(figsize=(6.3, 3.3))
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

ax.add_patch(Rectangle((1, 6), 30, 88, facecolor="#F7F9FC", edgecolor="#C9D6EA", linewidth=0.8))
ax.text(16, 90, "Windows 11 宿主机", ha="center", fontsize=8.2, fontweight="bold", color=BLUE)
ax.text(16, 84, "i7-10750H · 16 GB · NVMe SSD", ha="center", fontsize=6.6, color="#444444")
box(ax, 3, 52, 26, 26, "WSL2 Ubuntu 24.04\nGCC 13.3 · CMake\nLinux 5.15 (WSL2)", "white", BLUE, fs=7.1)
box(ax, 3, 22, 26, 24, "ext4 虚拟磁盘（VHDX）\n后端：NVMe SSD\nROTA=1（虚拟块设备）", "white", ORANGE, fs=6.9)
arrow(ax, 16, 52, 16, 46, color=GRAY)
ax.text(17, 48.5, "I/O", fontsize=6.2, color=GRAY)

box(ax, 34, 6, 29, 88,
    "课程仓库 fvs-course-lab\n\n"
    "adapters/  统一调用两套系统\n"
    "scripts/   下载、校验、正式实验\n"
    "patches/   GateANN AIO 补丁\n"
    "config/    固定参数\n"
    "systems/   PipeANN · GateANN\n"
    "datasets/  YFCC 1M（192D uint8）\n"
    "course_runs/ 索引与原始结果", "white", GREEN, fs=6.7)
ax.text(48.5, 90, "代码与数据", ha="center", fontsize=8.2, fontweight="bold", color=GREEN)

steps = [
    "① doctor\n校验 commit/数据/二进制",
    "② Debug 构建 10 万向量\n两系统各一次",
    "③ Debug PASS\n200 条查询、Recall ≥ 80%",
    "④ 下载/校验 Formal 索引",
    "⑤ 正式实验 3 轮 × 10 配置",
    "⑥ 聚合/绘图/报告",
]
for i, txt in enumerate(steps):
    y = 83 - i * 14
    box(ax, 67, y, 31, 11, txt, "white", PURPLE, fs=6.4)
    if i < len(steps) - 1:
        arrow(ax, 82.5, y, 82.5, y - 3, color=PURPLE, lw=0.9)
ax.text(82.5, 97, "实验流水线", ha="center", fontsize=8.2, fontweight="bold", color=PURPLE)
ax.text(1, 2, "注：WSL2 虚拟磁盘上的绝对延迟/QPS 不代表原生 NVMe；跨系统比较在同一环境内完成。",
        fontsize=6.0, color="#666666")
plt.tight_layout()
plt.savefig(os.path.join(OUT, "fig_platform.png"), dpi=300, bbox_inches="tight")
plt.close()

# ---------------- Fig 2-1 PipeANN-Filter
fig, ax = plt.subplots(figsize=(6.3, 4.2))
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

# storage summary
ax.add_patch(Rectangle((1, 86), 98, 12, facecolor="#FBF6F0", edgecolor="#E8D3BC", linewidth=0.8))
ax.text(2.5, 92, "SSD：Vamana 节点页（邻居 + 坐标 + 属性位）｜PQ 压缩向量", fontsize=7.4, va="center", color=ORANGE, fontweight="bold")
ax.add_patch(Rectangle((1, 72), 98, 12, facecolor="#F4F7FC", edgecolor="#C9D6EA", linewidth=0.8))
ax.text(2.5, 78, "DRAM：候选堆 / 开放列表｜布隆过滤器｜PQ 码本｜标签索引", fontsize=7.4, va="center", color=BLUE, fontweight="bold")

rows = [
    ("Pre-filter", "① 标签索引圈定候选 → ② PQ 粗排 → ③ 批量读 → ④ 精排",
     "读：节点页 + PQ 向量\n用：标签索引、PQ 码本、候选堆", GREEN),
    ("In-filter", "① best-first → ② 布隆粗筛 → ③ 可能合格才读 → ④ 真实验证",
     "读：节点页\n用：布隆过滤器、候选堆", BLUE),
    ("Post-filter", "① 先搜索 → ② 返回后再过滤",
     "读：节点页\n用：候选堆", GRAY),
]
for i, (name, process, data, color) in enumerate(rows):
    y = 50 - i * 19
    box(ax, 1, y, 15, 14, name, "white", color, fs=7.2, bold=True)
    box(ax, 19, y, 45, 14, process, "white", color, fs=6.6)
    box(ax, 67, y, 32, 14, data, "white", color, fs=6.5)
    arrow(ax, 16, y + 7, 19, y + 7, color=color, lw=1.0)
    arrow(ax, 64, y + 7, 67, y + 7, color=color, lw=1.0)

box(ax, 18, 2, 64, 9, "代价模型：SSD 读次数 × 10 + 距离比较次数 × 1", "#F7F7F7", GRAY, fs=6.8)
plt.tight_layout()
plt.savefig(os.path.join(OUT, "fig_pipeann.png"), dpi=300, bbox_inches="tight")
plt.close()

# ---------------- Fig 2-2 GateANN
fig, ax = plt.subplots(figsize=(6.3, 3.8))
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
ax.add_patch(Rectangle((1, 70), 98, 27, facecolor="#F4F7FC", edgecolor="#C9D6EA", linewidth=0.8))
ax.add_patch(Rectangle((1, 4), 98, 58, facecolor="#FBF6F0", edgecolor="#E8D3BC", linewidth=0.8))
ax.text(3, 94, "DRAM", fontsize=7.5, color=BLUE, fontweight="bold")
ax.text(3, 57, "SSD", fontsize=7.5, color=ORANGE, fontweight="bold")
box(ax, 5, 75, 28, 14, "SpmatFilterStore\n精确标签集（约 49 MB）", "white", BLUE, fs=6.6)
box(ax, 36, 75, 28, 14, "FullAdjIndex\n全邻居表（约 123 MB）", "white", BLUE, fs=6.6)
box(ax, 67, 75, 28, 14, "候选堆 / PQ 码本", "white", BLUE, fs=6.6)
box(ax, 20, 12, 34, 16, "Vamana 节点页\n邻居 + 坐标\n（不冗余存属性）", "white", ORANGE, fs=6.8)
box(ax, 58, 12, 34, 16, "距离计算 / 结果", "white", GRAY, fs=6.8)
arrow(ax, 20, 75, 37, 28, color=GREEN, lw=1.0, rad=-0.08)
ax.text(13, 48, "① 先查标签", fontsize=6.4, color=GREEN)
arrow(ax, 50, 75, 50, 28, color=ORANGE, lw=1.0)
ax.text(51, 60, "② 合格才读", fontsize=6.4, color=ORANGE)
arrow(ax, 54, 20, 58, 20, color=GRAY, lw=0.9)
ax.text(56, 22, "③ 计算", fontsize=6.2, color=GRAY)
ax.text(52, 66.0, "× 不合格：在 FullAdjIndex 中穿行，零 I/O", fontsize=6.2, color=GREEN)
ax.text(1, 1.0, "注：以额外 DRAM 结构换取 SSD 索引缩小与更少的无效 I/O；强过滤下穿行路径可能变长。",
        fontsize=6.0, color="#666666")
plt.tight_layout()
plt.savefig(os.path.join(OUT, "fig_gateann.png"), dpi=300, bbox_inches="tight")
plt.close()
print("done")
