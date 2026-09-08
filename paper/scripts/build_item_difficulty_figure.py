#!/usr/bin/env python3
"""Build the publication item-difficulty figure from the certified 840-cell table."""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
SOURCE = REPOSITORY / "ANALISI COMPLESSIVA" / "data" / "punteggi_modello_esercizio.csv"
OUTPUT = REPOSITORY / "PAPER" / "figures" / "item_difficulty.tex"


def main() -> None:
    with SOURCE.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))

    if len(rows) != 840:
        raise ValueError(f"Expected 840 balanced cells, found {len(rows)}")

    scores_by_item: dict[str, list[float]] = defaultdict(list)
    subject_by_item: dict[str, str] = {}
    for row in rows:
        item = row["item_key"]
        scores_by_item[item].append(float(row["item_accuracy"]))
        subject_by_item[item] = row["subject"]

    if len(scores_by_item) != 60:
        raise ValueError(f"Expected 60 exercises, found {len(scores_by_item)}")
    if any(len(scores) != 14 for scores in scores_by_item.values()):
        raise ValueError("Every exercise must contain exactly 14 model-cell scores")

    item_stats: list[tuple[float, str, float, float, float, float]] = []
    for item, scores in scores_by_item.items():
        ordered = sorted(scores)
        q1, _, q3 = statistics.quantiles(ordered, n=4, method="inclusive")
        item_stats.append(
            (
                statistics.mean(ordered),
                item,
                min(ordered),
                q1,
                q3,
                max(ordered),
            )
        )
    item_stats.sort(key=lambda row: (row[0], row[1]))

    plot_left = 12.0
    plot_width = 150.0
    plot_height = 42.0

    lines = [
        r"\begin{tikzpicture}[x=1mm,y=1mm,font=\scriptsize]",
        r"  \fill[lightgray!72] (12,37.8) rectangle (162,42);",
        r"  \node[font=\tiny,text=darkgray,anchor=east] at (161.5,39.9) {90--100 band};",
    ]

    for score in (0, 20, 40, 60, 80, 100):
        y = score * plot_height / 100
        lines.extend(
            [
                rf"  \draw[rulegray!48,line width=0.25pt] ({plot_left:.2f},{y:.2f}) -- ({plot_left + plot_width:.2f},{y:.2f});",
                rf"  \node[font=\tiny,text=darkgray,anchor=east] at ({plot_left - 1.4:.2f},{y:.2f}) {{{score}}};",
            ]
        )

    for rank in (1, 10, 20, 30, 40, 50, 60):
        x = plot_left + (rank - 1) * plot_width / 59
        lines.extend(
            [
                rf"  \draw[darkgray!65,line width=0.35pt] ({x:.2f},0) -- ({x:.2f},-1.15);",
                rf"  \node[font=\tiny,text=darkgray,anchor=north] at ({x:.2f},-1.65) {{{rank}}};",
            ]
        )

    for rank, (mean, item, minimum, q1, q3, maximum) in enumerate(item_stats, 1):
        x = plot_left + (rank - 1) * plot_width / 59
        color = "navy" if subject_by_item[item] == "analysis_3" else "gold!90!black"
        ymin = minimum * plot_height / 100
        yq1 = q1 * plot_height / 100
        ymean = mean * plot_height / 100
        yq3 = q3 * plot_height / 100
        ymax = maximum * plot_height / 100
        lines.extend(
            [
                rf"  \draw[darkgray!34,line width=0.28pt] ({x:.2f},{ymin:.2f}) -- ({x:.2f},{ymax:.2f});",
                rf"  \draw[{color},line width=1.05pt] ({x:.2f},{yq1:.2f}) -- ({x:.2f},{yq3:.2f});",
                rf"  \filldraw[fill={color},draw=white,line width=0.22pt] ({x:.2f},{ymean:.2f}) circle (0.72);",
            ]
        )

    lines.extend(
        [
            r"  \draw[darkgray,line width=0.45pt] (12,0) -- (162,0);",
            r"  \node[font=\scriptsize,rotate=90,text=ink] at (1.2,21) {Score (\%)};",
            r"  \node[font=\scriptsize,text=ink] at (87,-6.6) {Exercise rank, hardest to easiest};",
            r"  \filldraw[fill=navy,draw=white,line width=0.22pt] (25,47.2) circle (0.9);",
            r"  \node[font=\tiny,text=darkgray,anchor=west] at (27,47.2) {Analysis III};",
            r"  \filldraw[fill=gold!90!black,draw=white,line width=0.22pt] (55,47.2) circle (0.9);",
            r"  \node[font=\tiny,text=darkgray,anchor=west] at (57,47.2) {Physics II};",
            r"  \draw[darkgray!34,line width=0.28pt] (92,44.8) -- (92,49.6);",
            r"  \draw[navy,line width=1.05pt] (92,46.0) -- (92,48.4);",
            r"  \filldraw[fill=navy,draw=white,line width=0.22pt] (92,47.2) circle (0.72);",
            r"  \node[font=\tiny,text=darkgray,anchor=west] at (94,47.2) {mean; IQR; min--max};",
            r"\end{tikzpicture}",
            "",
        ]
    )

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
