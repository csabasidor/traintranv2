"""
Notebook 06 -- maps and figures for the manuscript (register PRE-4, PRE-5, PRE-6; R1: readable at page size,
consistent classifications, scales, symbols and country labels; R2: a key map, a conceptual diagram, high-resolution
maps with captions a reader can use without the text).

One style for every figure: ``STYLE`` (fonts, sizes), ``NETWORK_COLORS``, shared class breaks (``BREAKS``), a scale
bar, 300 dpi PNG + PDF via ``save``, and a caption registered with every saved figure (``captions.md``).
"""

import os

import numpy as np

STYLE = {"font.family": "DejaVu Sans", "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
         "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.spines.top": False,
         "axes.spines.right": False, "savefig.dpi": 300}
NETWORK_COLORS = {"domestic_direct": "#1b6ca8", "domestic_one_transfer": "#7fb3d5",
                  "foreign_direct": "#c0392b", "foreign_one_transfer": "#f1948a"}
COUNTRY_ORDER = ["SK", "CZ", "HU", "AT", "PL", "UA"]
# shared class breaks: every map of the same quantity uses the same classes, whatever the network
BREAKS = {"journeys_per_day": [0, 1, 2, 5, 10, 20, 50, np.inf],
          "share": [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0001],
          "rail_market": [0, 500, 1_000, 5_000, 20_000, 100_000, np.inf]}
CMAP = "YlGnBu"
METRIC_CRS = "EPSG:3035"
A4_WIDTH_IN = 7.0          # usable text width of an A4 journal page


def setup():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update(STYLE)
    return plt


class Captions:
    """Collects one caption per figure and writes them to captions.md beside the figures."""

    def __init__(self, folder):
        self.folder, self.items = folder, []

    def add(self, name, text):
        self.items.append((name, text))

    def write(self):
        p = os.path.join(self.folder, "captions.md")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("# Figure captions\n\n")
            for name, text in self.items:
                fh.write(f"**{name}** — {text}\n\n")
        return p


def save(fig, folder, name, captions: "Captions", caption: str):
    """300 dpi PNG and a PDF, and the caption registered."""
    os.makedirs(folder, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(folder, f"{name}.{ext}"), dpi=300, bbox_inches="tight")
    captions.add(name, caption)
    return os.path.join(folder, f"{name}.png")


def classify(values, breaks):
    """Class index per value for the shared breaks (NaN -> -1)."""
    v = np.asarray(values, float)
    idx = np.digitize(v, breaks[1:-1], right=False)
    return np.where(np.isnan(v), -1, idx)


def class_labels(breaks):
    """'a–b' per class, '≥ a' for the open top class (a break of 1.0001 is shown as 1: it only closes the top)."""
    out = []
    for a, b in zip(breaks[:-1], breaks[1:]):
        if not np.isfinite(b):
            out.append(f"≥ {a:,.6g}")
        else:
            out.append(f"{a:,.6g}–{round(b, 3):,.6g}")
    return out


def scale_bar(ax, length_km=100, loc=(0.05, 0.05)):
    """A plain scale bar for a map in a metric CRS (metres)."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x0 + loc[0] * (x1 - x0)
    y = y0 + loc[1] * (y1 - y0)
    ax.plot([x, x + length_km * 1000], [y, y], color="black", lw=2, solid_capstyle="butt")
    ax.text(x + length_km * 500, y + 0.012 * (y1 - y0), f"{length_km} km", ha="center", va="bottom", fontsize=7)


def choropleth(ax, gdf, column, breaks, title, background=None, cmap=CMAP, legend_title="", legend_loc="upper left",
               legend=True):
    """Classed choropleth with the shared breaks. The legend goes where the map has no data (upper left: outside the
    study countries) or, with legend=False, is left to the caller (returns the handles for a figure legend)."""
    import matplotlib.colors as mcolors
    from matplotlib.patches import Patch
    if background is not None:
        background.plot(ax=ax, color="#f2f2f2", edgecolor="#bdbdbd", linewidth=0.3)
    k = classify(gdf[column], breaks)
    colors = __import__("matplotlib").colormaps[cmap](np.linspace(0.15, 0.95, len(breaks) - 1))
    g = gdf.assign(_k=k)
    for i, c in enumerate(colors):
        part = g[g["_k"] == i]
        if len(part):
            part.plot(ax=ax, color=mcolors.to_hex(c), linewidth=0)
    ax.set_title(title)
    ax.set_axis_off()
    handles = [Patch(facecolor=mcolors.to_hex(c), label=l) for c, l in zip(colors, class_labels(breaks))]
    if legend:
        ax.legend(handles=handles, title=legend_title, loc=legend_loc, frameon=False)
    return handles
