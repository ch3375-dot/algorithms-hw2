"""Measure separate-chaining search costs and write comparison artifacts."""

import csv
import random
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.hash_table import ChainedHashTable


CAPACITY = 97
TARGET_LOAD_FACTORS = (0.25, 0.5, 1, 2, 4)
RANDOM_SEED = 2026
FAILURE_QUERY_COUNT = 10_000
RESULTS_DIRECTORY = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ExperimentRow:
    target_alpha: float
    actual_alpha: float
    bucket_count: int
    key_count: int
    successful_average_nodes: float
    successful_theory: float
    unsuccessful_average_nodes: float
    unsuccessful_theory: float


class CountingChainedHashTable(ChainedHashTable):
    """Count nodes actually inspected by the base table's get operation."""

    def __init__(self, capacity: int = CAPACITY) -> None:
        super().__init__(capacity)
        self.nodes_examined = 0

    def _pair_index(self, bucket, key):
        for index, (stored_key, _) in enumerate(bucket):
            self.nodes_examined += 1
            if stored_key == key:
                return index
        return None


def load_factor_key_count(alpha: float) -> int:
    """Return the nearest positive key count for a target load factor."""
    return max(1, int(CAPACITY * alpha + 0.5))


def generate_keys(count: int, seed: int, prefix: str) -> list[str]:
    generator = random.Random(seed)
    return [
        f"{prefix}-{index:04d}-{generator.getrandbits(64):016x}"
        for index in range(count)
    ]


def measure_search_costs(
    table: CountingChainedHashTable,
    present_keys: list[str] | tuple[str, ...],
    missing_keys: list[str] | tuple[str, ...],
) -> tuple[float, float]:
    if not present_keys:
        raise ValueError("at least one present key is required")
    if not missing_keys:
        raise ValueError("at least one missing key is required")

    successful_nodes = 0
    for key in present_keys:
        table.nodes_examined = 0
        if table.get(key) != key:
            raise AssertionError(f"unexpected value for key {key!r}")
        successful_nodes += table.nodes_examined

    unsuccessful_nodes = 0
    for key in missing_keys:
        table.nodes_examined = 0
        try:
            table.get(key)
        except KeyError:
            unsuccessful_nodes += table.nodes_examined
        else:
            raise AssertionError(f"expected missing key {key!r}")

    return (
        successful_nodes / len(present_keys),
        unsuccessful_nodes / len(missing_keys),
    )


def run_experiment(
    failure_query_count: int = FAILURE_QUERY_COUNT,
) -> list[ExperimentRow]:
    if failure_query_count <= 0:
        raise ValueError("failure_query_count must be greater than zero")

    rows = []
    for index, target_alpha in enumerate(TARGET_LOAD_FACTORS):
        key_count = load_factor_key_count(target_alpha)
        present_keys = generate_keys(key_count, RANDOM_SEED, "present")
        missing_keys = generate_keys(
            failure_query_count,
            RANDOM_SEED + 1,
            f"missing-{index}",
        )
        table = CountingChainedHashTable(capacity=CAPACITY)
        for key in present_keys:
            table.put(key, key)
        table.nodes_examined = 0

        successful_average, unsuccessful_average = measure_search_costs(
            table,
            present_keys,
            missing_keys,
        )
        actual_alpha = key_count / CAPACITY
        rows.append(
            ExperimentRow(
                target_alpha=target_alpha,
                actual_alpha=actual_alpha,
                bucket_count=CAPACITY,
                key_count=key_count,
                successful_average_nodes=successful_average,
                successful_theory=1 + target_alpha / 2,
                unsuccessful_average_nodes=unsuccessful_average,
                unsuccessful_theory=target_alpha,
            )
        )
    return rows


def render_markdown_table(rows: list[ExperimentRow]) -> str:
    lines = [
        "| 목표 α | 실측 α | 버킷 수 | 키 수 | 성공 탐색 실측 / 이론 | 실패 탐색 실측 / 이론 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row.target_alpha:g} | {row.actual_alpha:.4f} "
            f"| {row.bucket_count} | {row.key_count} "
            f"| {row.successful_average_nodes:.3f} / {row.successful_theory:.3f} "
            f"| {row.unsuccessful_average_nodes:.3f} / {row.unsuccessful_theory:.3f} |"
        )
    return (
        "이론값: 성공 1 + α/2, 실패 α (목표 α 기준)\n\n"
        + "\n".join(lines)
    )


def render_svg(rows: list[ExperimentRow]) -> str:
    width = 1000
    height = 560
    left = 90
    right = 950
    top = 60
    bottom = 425
    x_positions = [
        left + index * (right - left) / (len(rows) - 1)
        for index in range(len(rows))
    ]
    measurements = [
        value
        for row in rows
        for value in (
            row.successful_average_nodes,
            row.successful_theory,
            row.unsuccessful_average_nodes,
            row.unsuccessful_theory,
        )
    ]
    y_max = max(5.0, max(measurements) * 1.1)

    def y_position(value: float) -> float:
        return bottom - value * (bottom - top) / y_max

    series = (
        ("성공 실측", "#2563eb", None, "successful_average_nodes"),
        ("성공 이론 (1 + α/2)", "#2563eb", "8 5", "successful_theory"),
        ("실패 실측", "#dc2626", None, "unsuccessful_average_nodes"),
        ("실패 이론 (α)", "#dc2626", "8 5", "unsuccessful_theory"),
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        "<title>개별 체이닝 탐색 비교</title>",
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="500" y="30" text-anchor="middle" font-size="20">'
        "적재율별 평균 노드 비교</text>",
    ]

    for tick in range(6):
        value = y_max * tick / 5
        y = y_position(value)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" '
            'stroke="#d1d5db" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 12}" y="{y + 5:.1f}" text-anchor="end" '
            f'font-size="12">{value:.1f}</text>'
        )

    parts.extend(
        (
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" '
            'stroke="#111827"/>',
            f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" '
            'stroke="#111827"/>',
            f'<text x="{(left + right) / 2:.1f}" y="465" '
            'text-anchor="middle" font-size="14">목표 적재율 α</text>',
            f'<text x="22" y="{(top + bottom) / 2:.1f}" '
            'transform="rotate(-90 22 242)" text-anchor="middle" '
            'font-size="14">평균 방문 노드 수</text>',
        )
    )

    for x, row in zip(x_positions, rows):
        parts.append(
            f'<text x="{x:.1f}" y="{bottom + 24}" text-anchor="middle" '
            f'font-size="12">α={row.target_alpha:g}</text>'
        )

    legend_positions = (110, 340, 590, 790)
    for (label, color, dash, field), legend_x in zip(series, legend_positions):
        values = [getattr(row, field) for row in rows]
        points = " ".join(
            f"{x:.1f},{y_position(value):.1f}"
            for x, value in zip(x_positions, values)
        )
        dash_attribute = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" '
            f'stroke-width="2.5"{dash_attribute}/>'
        )
        for x, value in zip(x_positions, values):
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y_position(value):.1f}" '
                f'r="4" fill="{color}"/>'
            )
        parts.append(
            f'<line x1="{legend_x}" y1="510" x2="{legend_x + 28}" y2="510" '
            f'stroke="{color}" stroke-width="2.5"{dash_attribute}/>'
        )
        parts.append(
            f'<text x="{legend_x + 34}" y="515" font-size="12">'
            f"{escape(label)}</text>"
        )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def write_results(
    rows: list[ExperimentRow],
    csv_path: Path,
    svg_path: Path,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as result_file:
        writer = csv.writer(result_file, lineterminator="\n")
        writer.writerow(
            (
                "target_alpha",
                "actual_alpha",
                "bucket_count",
                "key_count",
                "successful_average_nodes",
                "successful_theory",
                "unsuccessful_average_nodes",
                "unsuccessful_theory",
            )
        )
        for row in rows:
            writer.writerow(
                (
                    f"{row.target_alpha:.2f}",
                    f"{row.actual_alpha:.6f}",
                    row.bucket_count,
                    row.key_count,
                    f"{row.successful_average_nodes:.6f}",
                    f"{row.successful_theory:.6f}",
                    f"{row.unsuccessful_average_nodes:.6f}",
                    f"{row.unsuccessful_theory:.6f}",
                )
            )
    svg_path.write_text(render_svg(rows), encoding="utf-8")


def main() -> None:
    rows = run_experiment()
    csv_path = RESULTS_DIRECTORY / "results.csv"
    svg_path = RESULTS_DIRECTORY / "results.svg"
    write_results(rows, csv_path, svg_path)

    print(
        "버킷 수는 97이며, 0.25와 0.5는 정수 키 개수로 정확히 만들 수 없어 "
        "가장 가까운 키 개수를 사용했습니다."
    )
    print("이론값은 목표 α를 기준으로 계산했습니다.")
    print(render_markdown_table(rows))
    print(f"\nCSV: {csv_path.relative_to(PROJECT_ROOT)}")
    print(f"SVG: {svg_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
