from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import json
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.cm as cm


def plot():
    with open("swesynth/results.jsonl", "r") as f:
        data = f.readlines()

    data = [json.loads(line) for line in data]

    # Create DataFrame and sort by count
    df = pd.DataFrame(list(data.items()), columns=["Element", "Count"])
    df = df.sort_values(by="Count", ascending=False)

    # Select top 21 elements, excluding the first and "="
    # num_top = 21
    num_top = 27
    _df = df.iloc[1:]
    _df = _df.query('~(Element == "=")')
    top_10 = _df.head(num_top)

    # Aggregate remaining elements into "Others"
    others = _df.iloc[num_top:]["Count"].sum()
    top_10 = pd.concat([top_10, pd.DataFrame([["Others", others]], columns=["Element", "Count"])], ignore_index=True)

    # Function to format element names with line breaks
    def format_element_name(element):
        if "_" in element:
            return element.replace("_", "\n")
        return element

    # Calculate percentages
    total = top_10["Count"].sum()
    top_10["Percentage"] = top_10["Count"] / total * 100
    top_10["FormattedElement"] = top_10["Element"].apply(format_element_name)

    # Split data into large and small segments based on 3.5% threshold
    threshold = 3.5
    small_segments = top_10[top_10["Percentage"] < threshold].copy()
    large_segments = top_10[top_10["Percentage"] >= threshold].copy()

    # Find the "Others" row and separate it from large_segments
    others_row = large_segments[large_segments["Element"] == "Others"]
    large_segments_no_others = large_segments[large_segments["Element"] != "Others"]

    # Combine segments: large (without Others), small, then Others
    all_segments = pd.concat([large_segments_no_others, small_segments, others_row])

    # Use Seaborn's pastel color palette
    n_colors = len(all_segments)
    colors = sns.color_palette("pastel", n_colors)

    # Find the index of "Others" in the new order (it’s now at the end)
    others_idx = len(all_segments) - 1 if not others_row.empty else -1

    # Make "Others" segment a distinct color
    if others_idx >= 0:
        colors[others_idx] = (0.85, 0.37, 0.0)  # Dark orange for "Others"

    # Create explode effect with more separation for "Others"
    explode = [0.02] * len(all_segments)
    if others_idx >= 0:
        explode[others_idx] = 0.15  # More explode for "Others" segment

    # Custom wedgeprops
    wedgeprops = {"edgecolor": "white", "linewidth": 1.0, "antialiased": True}

    # Create the pie chart
    plt.figure(figsize=(14, 10), facecolor="white")

    def autopct_format(pct):
        return f"{pct:.1f}%" if pct >= threshold else ""

    # Draw the pie chart with shadow
    wedges, texts, autotexts = plt.pie(
        all_segments["Count"],
        labels=None,
        autopct=autopct_format,
        # pctdistance=0.5,
        pctdistance=0.65,
        startangle=90,
        colors=colors,
        explode=explode,
        # shadow=True,  # Add shadow
        wedgeprops=wedgeprops,
        textprops={"fontsize": 14, "fontweight": "bold", "color": "black"},
    )

    # Apply styling to the "Others" wedge
    if others_idx >= 0:
        wedges[others_idx].set_edgecolor("white")
        wedges[others_idx].set_linewidth(2.0)
        wedges[others_idx].set_hatch("///")

    # Format percentage texts
    for text in autotexts:
        text.set_fontsize(14)
        text.set_fontweight("bold")
        text.set_color("black")

    # Annotate large segments (excluding "Others" if it was in large_segments originally)
    for i, (wedge, row) in enumerate(zip(wedges[: len(large_segments_no_others)], large_segments_no_others.iterrows())):
        ang = (wedge.theta2 - wedge.theta1) / 2.0 + wedge.theta1
        x = np.cos(np.deg2rad(ang))
        y = np.sin(np.deg2rad(ang))
        horizontalalignment = {-1: "right", 1: "left"}[int(np.sign(x))]
        connectionstyle = f"angle,angleA=0,angleB={ang}"

        if row[1]["Element"] == "expression_statement":
            dist_mult = 1.05
            connectionstyle = "arc3,rad=0"
        elif row[1]["Percentage"] > 15:
            dist_mult = 1.05
        else:
            dist_mult = 1.15

        plt.annotate(
            f"{row[1]['FormattedElement']}",
            xy=(x, y),
            xytext=(dist_mult * x, dist_mult * y),
            fontsize=15,
            fontweight="bold",
            horizontalalignment=horizontalalignment,
            arrowprops=dict(arrowstyle="-", connectionstyle=connectionstyle, color="black", lw=1.2),
        )

    # Annotate "Others" separately if it exists
    if others_idx >= 0:
        wedge = wedges[others_idx]
        row = all_segments.iloc[others_idx]
        ang = (wedge.theta2 - wedge.theta1) / 2.0 + wedge.theta1
        x = np.cos(np.deg2rad(ang))
        y = np.sin(np.deg2rad(ang))
        horizontalalignment = {-1: "right", 1: "left"}[int(np.sign(x))]
        connectionstyle = f"angle,angleA=0,angleB={ang}"
        dist_mult = 1.25  # Special distance for "Others"

        plt.annotate(
            f"{row['FormattedElement']}",
            xy=(x, y),
            xytext=(dist_mult * x, dist_mult * y),
            fontsize=15,
            fontweight="bold",
            horizontalalignment=horizontalalignment,
            arrowprops=dict(arrowstyle="-", connectionstyle=connectionstyle, color="black", lw=1.2),
        )

    # Create legend labels for small segments only
    small_legend_labels = [f"{row['Element']}: {row['Percentage']:.1f}%" for _, row in small_segments.iterrows()]

    # Add a legend for small segments
    if not small_legend_labels:
        small_legend_labels = ["No segments < 3.5%"]

    plt.legend(
        wedges[len(large_segments_no_others) : len(large_segments_no_others) + len(small_segments)],  # Small segments only
        small_legend_labels,
        title="Small segments (< 3.5%)",
        loc="center left",
        bbox_to_anchor=(1.05, 0.5),
        fontsize=15,
        title_fontsize=20,
    )

    # Ensure circular shape and adjust layout
    plt.axis("equal")
    plt.subplots_adjust(left=0.1, right=0.7)

    # Show the chart
    # plt.show()
    plt.savefig("fixed-stmts-improved.pdf", bbox_inches="tight", pad_inches=0)


if __name__ == "__main__":
    plot()
