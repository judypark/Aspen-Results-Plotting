"""
Sensitivity results plotter for the DRI shaft furnace model.

Usage:
    Edit the "Run settings" below, then run: python plots.py

For each unique entry in "variables" (after filtering "option"), makes:
    1. Emissions          - grid of dual-axis subplots (metallization vs each emi_ column)
    2. DRI Composition    - stacked lines of DRImassfrac_ columns (%)
    3. Design Constraints - grid of dual-axis subplots (metallization vs each constraint_ column)
"""

import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import to_hex
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# ---------------------------------------------------------------------------
# Run settings
# ---------------------------------------------------------------------------
FILEPATH = "Sensitivity_results(2).xlsx"  # path to the results Excel file
SHEET = "results"
OPTION = "base"                         # value to filter the 'option' column by
OUTDIR = "plots"
SHOW = False                            # display figures interactively

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
X_COL = "value"
VAR_COL = "variable"
OPTION_COL = "option"
STATUS_COL = "status"
CENTRAL_COL = "central"
MET_COL = "metallization_fraction"

ERROR_STATUS = "errors"            # compared case-insensitively
ERROR_ZONE_COLOR = "red"
ERROR_ZONE_ALPHA = 0.3
CENTRAL_EDGE_COLOR = "darkgray"
CENTRAL_EDGE_WIDTH = 1.5

FIG_MIN, FIG_MAX = 6, 10           # figure width/height limits (inches)

sns.set_theme(context="talk", style="ticks", palette="tab10")
PALETTE = [c for c in map(to_hex, plt.rcParams["axes.prop_cycle"].by_key()["color"])
           if c != "#bcbd22"]                                  # tab10 minus yellow-olive
BASE_MS = plt.rcParams["lines.markersize"]                     # talk-context size
MET_COLOR = "#404040"                                          # dark gray


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def plot_series(ax, x, y, color, central):
    """Line through all points, circle markers, square for the central point."""
    ax.plot(x, y, "-", color=color, zorder=2)
    ax.plot(x[~central], y[~central], ls="none", marker="o", ms=BASE_MS,
            mfc=color, mew=0, zorder=3)
    ax.plot(x[central], y[central], ls="none", marker="s", ms=BASE_MS + 1,
            mfc=color, mec=CENTRAL_EDGE_COLOR, mew=CENTRAL_EDGE_WIDTH, zorder=4)


def make_figure(sub, variable, prefix, title, central, zones=()):
    """Dual-axis grid (metallization vs each prefixed column), or the stacked
    DRI composition plot when prefix == 'DRImassfrac_'."""
    ycols = [c for c in sub.columns if str(c).startswith(prefix)]
    if not ycols:
        print(f"  [skip] no columns starting with '{prefix}'")
        return None

    x = sub[X_COL].to_numpy()
    labels = [str(c).split("_", 1)[-1] for c in ycols]   # text after first underscore
    stacked = prefix == "DRImassfrac_"
    colors = [PALETTE[i % len(PALETTE)] for i in range(len(ycols))]
    handles = [] if stacked else [Line2D([0], [0], color=MET_COLOR, marker="o", mew=0,
                                         ms=BASE_MS, label="Metallization")]
    handles += [Line2D([0], [0], color=c, marker="o", mew=0, ms=BASE_MS, label=l)
                for c, l in zip(colors, labels)]
    if zones:
        handles.append(Patch(color=ERROR_ZONE_COLOR, alpha=ERROR_ZONE_ALPHA, lw=0,
                             label="Error zone"))
    shade = lambda ax: [ax.axvspan(lo, hi, color=ERROR_ZONE_COLOR, alpha=ERROR_ZONE_ALPHA,
                                   lw=0, zorder=0) for lo, hi in zones]

    if stacked:
        fig, ax = plt.subplots(figsize=(9, 7), constrained_layout=True)
        cumulative = np.cumsum(sub[ycols].fillna(0).to_numpy() * 100, axis=1)
        for i, color in enumerate(colors):
            plot_series(ax, x, cumulative[:, i], color, central)
        shade(ax)
        ax.axhline(100, color="black", lw=1.5, zorder=1)
        ax.set_ylim(0, 100)
        ax.set_xlabel(variable)
        ax.set_ylabel("%")
        fig.suptitle(f"{title}: {variable}")
        fig.legend(handles=handles, loc="outside right center", frameon=False)
        return fig

    ncols = math.ceil(math.sqrt(len(ycols)))
    nrows = math.ceil(len(ycols) / ncols)
    fig, axes = plt.subplots(
        nrows, ncols, squeeze=False, constrained_layout=True,
        figsize=(min(FIG_MAX, max(FIG_MIN, 4.5 * ncols)),
                 min(FIG_MAX, max(FIG_MIN, 3.8 * nrows + 1))))
    met = sub[MET_COL].to_numpy() * 100

    for ax, col, color in zip(axes.flat, ycols, colors):
        shade(ax)
        plot_series(ax, x, met, MET_COLOR, central)
        ax.set_xlabel(variable)
        ax.set_ylabel("Metallization (%)", color=MET_COLOR)
        ax.tick_params(axis="y", colors=MET_COLOR)

        # 'emi_kg_tonDRI_SO2' -> 'kg/tonDRI SO2'
        parts = str(col)[len(prefix):].split("_", 2)
        ylabel = (f"{parts[0]}/{parts[1]} {parts[2].replace('_', ' ')}" if len(parts) == 3
                  else " ".join(parts))
        ax2 = ax.twinx()
        plot_series(ax2, x, sub[col].to_numpy(), color, central)
        ax2.set_ylabel(ylabel, color=color)
        ax2.tick_params(axis="y", colors=color)

    empty = axes.flat[len(ycols):]
    for ax in empty[1:]:
        ax.remove()

    fig.suptitle(f"{title}: {variable}")
    if len(empty):   # free grid slot (odd count): vertical legend inside it
        empty[0].axis("off")
        empty[0].legend(handles=handles, loc="center", ncol=1, frameon=True)
    else:
        fig.legend(handles=handles, loc="outside lower center",
                   ncol=min(len(handles), 4), frameon=True)
    return fig


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(filepath, sheet="results", option="base", outdir="plots", show=False):
    df = pd.read_excel(filepath, sheet_name=sheet)
    df = df[df[OPTION_COL].astype(str).str.strip() == option]
    if df.empty:
        raise ValueError(f"No rows with {OPTION_COL} == '{option}'")

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    safe = lambda s: re.sub(r"[^\w.-]", "_", str(s))

    variables = df[VAR_COL].dropna().unique()
    print(f"Option '{option}': {len(variables)} variables -> {list(variables)}")

    for variable in variables:
        sub = df[df[VAR_COL] == variable]
        false = pd.Series(False, index=sub.index)
        central = (sub[CENTRAL_COL].astype(str).str.strip().str.upper()
                   .isin(["TRUE", "1", "1.0", "YES"]) if CENTRAL_COL in sub else false)
        error = (sub[STATUS_COL].astype(str).str.strip().str.lower() == ERROR_STATUS
                 if STATUS_COL in sub else false)
        # Drop error rows entirely ('central' takes precedence if a row is both).
        keep = central | ~error
        error_x = sub.loc[~keep, X_COL].to_numpy()
        sub, central = sub[keep], central[keep]
        order = sub[X_COL].argsort().values
        sub = sub.iloc[order].reset_index(drop=True)
        central = central.iloc[order].values
        print(f"Plotting '{variable}' ({len(sub)} points, {int((~keep).sum())} errors dropped)")

        # Error zones: span between the kept neighbours around each dropped point.
        xk = sub[X_COL].to_numpy()
        zones = sorted({(xk[xk < ex].max() if (xk < ex).any() else ex,
                         xk[xk > ex].min() if (xk > ex).any() else ex)
                        for ex in error_x})

        for tag, prefix, title in [
            ("1_emissions", "emi_", "Emissions"),
            ("2_dri_composition", "DRImassfrac_", "DRI Composition"),
            ("3_design_constraints", "constraint_", "Design Constraints"),
        ]:
            fig = make_figure(sub, variable, prefix, title, central, zones)
            if fig is None:
                continue
            path = out / f"{safe(option)}_{safe(variable)}_{tag}.png"
            fig.savefig(path, dpi=200, bbox_inches="tight")
            print(f"  saved {path}")
            if not show:
                plt.close(fig)

    if show:
        plt.show()


if __name__ == "__main__":
    main(FILEPATH, SHEET, OPTION, OUTDIR, SHOW)
