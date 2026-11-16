"""Figure for the README: early stopping keeps classification cost flat.

Input: docs/figures/early_stopping_pages.csv — per-document page counts from
the production batch run (two integers per row, no identifying data).
"""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "docs" / "figures"
SURFACE, INK, INK2, GRID, BLUE = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"

rows = [(int(r["total_pages"]), int(r["pages_classified"])) for r in csv.DictReader(open(FIG / "early_stopping_pages.csv"))]
total, classified = sum(t for t, _ in rows), sum(c for _, c in rows)

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
fig, ax = plt.subplots(figsize=(8, 4.6), dpi=200, facecolor=SURFACE)
ax.set_facecolor(SURFACE)
lim = max(t for t, _ in rows) + 4
ax.plot([0, lim], [0, lim], color=INK2, lw=1, ls=(0, (4, 3)), zorder=1)
ax.text(66, 74, "without early stopping\n(every page classified)", color=INK2, ha="right", va="center", fontsize=9)
ax.scatter([t for t, _ in rows], [c for _, c in rows], s=26, color=BLUE, alpha=0.55,
           edgecolors=SURFACE, linewidths=0.8, zorder=2)
ax.set_xlim(0, lim); ax.set_ylim(0, lim * 0.62)
ax.set_xlabel("Pages in the filing", color=INK2)
ax.set_ylabel("Pages sent to the classifier", color=INK2)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color(GRID)
ax.tick_params(colors=INK2, length=0)
ax.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
fig.suptitle("Early stopping keeps classification cost flat as filings get longer", x=0.07, ha="left",
             color=INK, fontsize=12, fontweight="bold")
ax.set_title(f"{len(rows)} production filings · {total:,} pages · {classified:,} classified "
             f"({100 * (1 - classified / total):.1f}% of classification calls avoided)",
             loc="left", color=INK2, fontsize=9, pad=10)
fig.tight_layout()
fig.savefig(FIG / "early_stopping.png", facecolor=SURFACE)
print("saved", FIG / "early_stopping.png")
