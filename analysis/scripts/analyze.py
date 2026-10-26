"""
Course experiment analysis: generate all figures and summary tables.
Input:  data/results_main.csv (30 rows) + data/results_supp_low_L.csv
Output: figures/*.png
"""
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if not (BASE / 'data').is_dir():
    _wsl = Path('/home/user/fvs-course-lab/analysis')
    if _wsl.is_dir():
        BASE = _wsl
FIG = BASE / 'figures'
FIG.mkdir(exist_ok=True)

plt.rcParams.update({
    'font.size': 10,
    'axes.titlesize': 11,
    'axes.labelsize': 10,
    'legend.fontsize': 9,
    'figure.dpi': 150,
})

main = pd.read_csv(BASE / 'data/results_main.csv')
# Prefer the 3-repeat aggregate when present; otherwise fall back to the single-run CSV.
_supp3 = BASE / 'data/results_supp_low_L_3runs.csv'
supp = pd.read_csv(_supp3 if _supp3.is_file() else BASE / 'data/results_supp_low_L.csv')
SUPP_3RUNS = _supp3.is_file() and 'recall_percent_median' in supp.columns

# ---- aggregate main: median over 3 repeats ----
g = main.groupby(['system','bucket','L']).agg(
    recall_med=('recall_percent','median'),
    recall_min=('recall_percent','min'),
    recall_max=('recall_percent','max'),
    lat_med=('mean_latency_us','median'),
    lat_min=('mean_latency_us','min'),
    lat_max=('mean_latency_us','max'),
    qps_med=('qps','median'),
    ios_med=('mean_ios','median'),
    ios_min=('mean_ios','min'),
    ios_max=('mean_ios','max'),
    skips=('filter_skips','median'),
    tunnel=('tunnel_time_us','median'),
    io_us=('io_time_us','median'),
    proc=('process_time_us','median'),
    pre=('pre_filter_queries','median'),
    in_q=('in_filter_queries','median'),
    post=('post_filter_queries','median'),
    fp=('filter_false_positives','median'),
    rss=('peak_rss_kb','median'),
    idx=('index_bytes','median'),
).reset_index()

# ============ Fig 1: Recall-Latency (High bucket) ============
fig, ax = plt.subplots(figsize=(7,4.5))
for sysn, color, mk in [('pipeann','#1f77b4','o'),('gateann','#ff7f0e','s')]:
    s = g[(g.system==sysn)&(g.bucket=='high')].sort_values('L')
    ax.errorbar(s.lat_med/1000, s.recall_med,
                xerr=[(s.lat_med-s.lat_min)/1000, (s.lat_max-s.lat_med)/1000],
                yerr=[s.recall_med-s.recall_min, s.recall_max-s.recall_med],
                color=color, marker=mk, label=sysn, capsize=3, lw=2, ms=8)
    for _,r in s.iterrows():
        ax.annotate(f'L={int(r.L)}', (r.lat_med/1000, r.recall_med),
                    textcoords='offset points', xytext=(8,5), fontsize=8, color=color)
ax.set_xlabel('Mean Query Latency (ms)')
ax.set_ylabel('Recall@10 (%)')
ax.set_title('Fig.1  Recall-Latency Tradeoff on High-Selectivity Bucket (median of 3 runs)')
ax.legend(); ax.grid(True, alpha=0.3)
plt.tight_layout(); plt.savefig(FIG/'fig1_recall_latency.png', dpi=150); plt.close()

# ============ Fig 2: Selectivity sensitivity ============
fig, axes = plt.subplots(1,3, figsize=(13,4))
buckets = ['low','medium','high']
sel = {'low':0.545,'medium':2.958,'high':12.323}
for sysn, color, repL in [('pipeann','#1f77b4',40),('gateann','#ff7f0e',320)]:
    s = g[(g.system==sysn)&(g.L==repL)&(g.bucket.isin(buckets))].set_index('bucket').reindex(buckets)
    xs = [sel[b] for b in buckets]
    axes[0].plot(xs, s.recall_med.values, color=color, marker='o', label=sysn, lw=2, ms=7)
    axes[1].plot(xs, s.lat_med.values/1000, color=color, marker='s', label=sysn, lw=2, ms=7)
    axes[2].plot(xs, s.ios_med.values, color=color, marker='^', label=sysn, lw=2, ms=7)
axes[0].set_title('Recall@10'); axes[0].set_ylabel('%')
axes[1].set_title('Mean Latency'); axes[1].set_ylabel('ms')
axes[2].set_title('Mean Logical I/O'); axes[2].set_ylabel('I/O / query')
for ax in axes:
    ax.set_xlabel('Selectivity (%)'); ax.legend(); ax.grid(True, alpha=0.3)
plt.suptitle('Fig.2  Selectivity Sensitivity (PipeANN L=40, GateANN L=320)', y=1.02)
plt.tight_layout(); plt.savefig(FIG/'fig2_selectivity.png', dpi=150, bbox_inches='tight'); plt.close()

# ============ Fig 3: Supplemental — GateANN Low-bucket L scan ============
low_main = g[(g.system=='gateann')&(g.bucket=='low')].iloc[0]

rows = []
if SUPP_3RUNS:
    for _, r in supp.iterrows():
        rows.append(dict(
            L=int(r['L']),
            recall=r['recall_percent_median'], rlo=r['recall_percent_min'], rhi=r['recall_percent_max'],
            io=r['mean_ios_median'], ilo=r['mean_ios_min'], ihi=r['mean_ios_max'],
            lat=r['mean_latency_us_median'], llo=r['mean_latency_us_min'], lhi=r['mean_latency_us_max'],
            skips=r['filter_skips_median'], tunnel=r.get('tunnel_time_us_median', float('nan')),
        ))
else:
    for _, r in supp.iterrows():
        rows.append(dict(
            L=int(r['L']),
            recall=r['recall_percent'], rlo=r['recall_percent'], rhi=r['recall_percent'],
            io=r['mean_ios'], ilo=r['mean_ios'], ihi=r['mean_ios'],
            lat=r['mean_latency_us'], llo=r['mean_latency_us'], lhi=r['mean_latency_us'],
            skips=r['filter_skips'], tunnel=r.get('tunnel_time_us', float('nan')),
        ))
# L=320 reference: from the supplemental batch when present, else from the formal experiment.
if not any(r['L'] == 320 for r in rows):
    rows.append(dict(
        L=320,
        recall=low_main.recall_med, rlo=low_main.recall_min, rhi=low_main.recall_max,
        io=low_main.ios_med, ilo=low_main.ios_min, ihi=low_main.ios_max,
        lat=low_main.lat_med, llo=low_main.lat_min, lhi=low_main.lat_max,
        skips=low_main.skips, tunnel=low_main.tunnel,
    ))
rows.sort(key=lambda r: r['L'])
sdf = pd.DataFrame(rows)

fig, ax1 = plt.subplots(figsize=(7,4.5))
color1 = '#ff7f0e'
ax1.errorbar(sdf.L, sdf.recall,
             yerr=[sdf.recall - sdf.rlo, sdf.rhi - sdf.recall],
             fmt='o-', color=color1, lw=2, ms=8, capsize=4, label='Recall@10')
ax1.set_xlabel('Search Budget L'); ax1.set_ylabel('Recall@10 (%)', color=color1)
ax1.tick_params(axis='y', labelcolor=color1)
ax1.set_ylim(0, 100)
ax1.set_xticks(list(sdf.L))
for _, r in sdf.iterrows():
    ax1.annotate(f'{r.recall:.1f}%', (r.L, r.recall), textcoords='offset points',
                 xytext=(0,13), ha='center', color=color1, fontsize=9)
ax2 = ax1.twinx()
color2 = '#2ca02c'
ax2.errorbar(sdf.L, sdf.io, yerr=[sdf.io - sdf.ilo, sdf.ihi - sdf.io],
             fmt='s--', color=color2, lw=2, ms=8, capsize=4, label='Mean I/O')
ax2.set_ylabel('Mean logical I/O / query', color=color2)
ax2.tick_params(axis='y', labelcolor=color2)
top = sdf.iloc[-1]
_hi = g[(g.system == 'gateann') & (g.bucket == 'high') & (g.L == 320)]
_hi_txt = f"{_hi.recall_med.iloc[0]:.1f}%" if len(_hi) else "93.2%"
ax1.set_title(
    'Fig.3  Supplemental: GateANN L-scan on Low-Selectivity Bucket (0.545%)\n'
    f'L={int(top.L)} ({int(top.L)//320}x budget) reaches {top.recall:.1f}%, '
    f'still below High bucket {_hi_txt} at L=320'
    + ('  (median of 3 runs, bars = min-max)' if SUPP_3RUNS else '  (single run)'),
    fontsize=10,
)
ax1.grid(True, alpha=0.3)
fig.tight_layout(); plt.savefig(FIG/'fig3_gateann_low_L_scan.png', dpi=150, bbox_inches='tight'); plt.close()

# ============ Fig 4: GateANN time breakdown ============
fig, ax = plt.subplots(figsize=(7,4.5))
buckets_g = ['low','medium','high']
# for high, use L=320 representative
def get_gtime(b, L=320):
    r = g[(g.system=='gateann')&(g.bucket==b)&(g.L==L)]
    if len(r)==0: return None
    return r.iloc[0]
labels = []
io_t=[]; tun_t=[]; proc_t=[]
for b in buckets_g:
    r = get_gtime(b)
    labels.append(f'{b}\n(sel={sel[b]:.2f}%)')
    io_t.append(r.io_us); tun_t.append(r.tunnel); proc_t.append(r.proc)
x = np.arange(len(labels))
ax.bar(x, io_t, label='I/O wait', color='#d62728')
ax.bar(x, tun_t, bottom=io_t, label='Graph Tunneling', color='#ff7f0e')
ax.bar(x, proc_t, bottom=np.array(io_t)+np.array(tun_t), label='Process / distance', color='#1f77b4')
ax.set_xticks(x); ax.set_xticklabels(labels)
ax.set_ylabel('Time per query (us)')
ax.set_title('Fig.4  GateANN Per-Query Time Breakdown (L=320)\nOn strong filter, tunnel dominates; on weak filter, I/O dominates')
ax.legend(); ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout(); plt.savefig(FIG/'fig4_gateann_time_breakdown.png', dpi=150); plt.close()

# ============ Fig 5: PipeANN routing + false positives ============
fig, ax1 = plt.subplots(figsize=(7,4.5))
buckets_p = ['low','medium','high']
fp_vals = []; io_p = []; route_pre = []
for b in buckets_p:
    r = g[(g.system=='pipeann')&(g.bucket==b)&(g.L==40)].iloc[0]
    fp_vals.append(r.fp); io_p.append(r.ios_med)
    route_pre.append(r.pre)  # 200 if Pre-filter, 0 otherwise
xs = np.arange(len(buckets_p))
ax1.bar(xs-0.2, fp_vals, 0.4, color='#9467bd', label='False positives / query')
ax1.set_ylabel('False positives / query', color='#9467bd')
ax1.tick_params(axis='y', labelcolor='#9467bd')
ax2 = ax1.twinx()
ax2.bar(xs+0.2, io_p, 0.4, color='#17becf', label='Mean I/O / query')
ax2.set_ylabel('Mean I/O / query', color='#17becf')
ax2.tick_params(axis='y', labelcolor='#17becf')
ax1.set_xticks(xs)
ax1.set_xticklabels([f'{b}\nsel={sel[b]:.2f}%\n{"Pre-filter" if route_pre[i]==200 else "In-filter"}' for i,b in enumerate(buckets_p)])
ax1.set_title('Fig.5  PipeANN-Filter Routing Switch & False Positives (L=40)\nLow: all Pre-filter (FP=0); Medium/High: all In-filter')
ax1.grid(True, alpha=0.3, axis='y')
plt.tight_layout(); plt.savefig(FIG/'fig5_pipeann_routing_fp.png', dpi=150); plt.close()

# ============ Print summary ============
print('=== Main experiment summary (median) ===')
print(g[['system','bucket','L','recall_med','lat_med','ios_med','skips','tunnel','io_us','proc','fp','pre','in_q']].to_string(index=False))
print()
print('=== Supplemental: GateANN Low-bucket L scan ===')
print(f'({"3 repeats" if SUPP_3RUNS else "single run"})')
for _, r in sdf.iterrows():
    print(f'L={int(r.L):>5}: recall={r.recall:.2f} [{r.rlo:.2f}-{r.rhi:.2f}]  '
          f'lat={r.lat:.0f}us [{r.llo:.0f}-{r.lhi:.0f}]  '
          f'io={r.io:.2f} [{r.ilo:.2f}-{r.ihi:.2f}]  skips={r.skips:.1f}  tunnel={r.tunnel:.0f}us')
print()
print('All figures saved to', FIG)
