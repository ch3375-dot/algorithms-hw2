"""Compare separate chaining and linear probing at matching load factors."""

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
from src.linear_probing import LinearProbingHashTable


CAPACITY = 97
TARGET_LOAD_FACTORS = tuple(step / 10 for step in range(1, 10))
RANDOM_SEED = 2026
FAILURE_QUERY_COUNT = 10_000
RESULTS_DIRECTORY = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ComparisonRow:
    target_alpha: float
    actual_alpha: float
    bucket_count: int
    key_count: int
    chaining_successful_actual: float
    chaining_successful_theory: float
    chaining_unsuccessful_actual: float
    chaining_unsuccessful_theory: float
    linear_successful_actual: float
    linear_successful_theory: float
    linear_unsuccessful_actual: float
    linear_unsuccessful_theory: float


def _key_count(alpha: float) -> int:
    return max(1, int(CAPACITY * alpha + 0.5))


def _generate_keys(count: int, seed: int, prefix: str) -> list[str]:
    generator = random.Random(seed)
    return [
        f"{prefix}-{index:04d}-{generator.getrandbits(64):016x}"
        for index in range(count)
    ]


def _home_slot(key: str, capacity: int) -> int:
    value = 0
    for byte in key.encode("utf-8"):
        value = (31 * value + byte) % capacity
    return value


def _measure_chaining(
    table: ChainedHashTable,
    present_keys: list[str],
    missing_keys: list[str],
) -> tuple[float, float]:
    successful_comparisons = 0
    for key in present_keys:
        bucket = table.buckets[table._bucket_index(key)]
        for stored_key, _ in bucket:
            successful_comparisons += 1
            if stored_key == key:
                break
        else:
            raise AssertionError(f"inserted key was not found: {key!r}")

    unsuccessful_comparisons = 0
    for key in missing_keys:
        bucket = table.buckets[table._bucket_index(key)]
        for stored_key, _ in bucket:
            unsuccessful_comparisons += 1
            if stored_key == key:
                raise AssertionError(f"missing key was found: {key!r}")

    return (
        successful_comparisons / len(present_keys),
        unsuccessful_comparisons / len(missing_keys),
    )


def _measure_linear_probing(
    table: LinearProbingHashTable,
    present_keys: list[str],
    missing_keys: list[str],
) -> tuple[float, float]:
    successful_probes = 0
    for key in present_keys:
        index = _home_slot(key, table.capacity)
        for _ in range(table.capacity):
            entry = table.buckets[index]
            successful_probes += 1
            if entry is None:
                raise AssertionError(f"inserted key was not found: {key!r}")
            if entry[0] == key:
                break
            index = (index + 1) % table.capacity
        else:
            raise AssertionError(f"probe cycle did not find key: {key!r}")

    unsuccessful_probes = 0
    for key in missing_keys:
        index = _home_slot(key, table.capacity)
        for _ in range(table.capacity):
            entry = table.buckets[index]
            unsuccessful_probes += 1
            if entry is None:
                break
            if entry[0] == key:
                raise AssertionError(f"missing key was found: {key!r}")
            index = (index + 1) % table.capacity
        else:
            raise AssertionError(f"probe cycle had no empty slot for {key!r}")

    return (
        successful_probes / len(present_keys),
        unsuccessful_probes / len(missing_keys),
    )


def run_experiment(
    failure_query_count: int = FAILURE_QUERY_COUNT,
) -> list[ComparisonRow]:
    if failure_query_count <= 0:
        raise ValueError("failure_query_count must be greater than zero")

    max_key_count = _key_count(TARGET_LOAD_FACTORS[-1])
    all_present_keys = _generate_keys(max_key_count, RANDOM_SEED, "present")
    missing_keys = _generate_keys(
        failure_query_count,
        RANDOM_SEED + 1,
        "missing",
    )
    rows = []

    for target_alpha in TARGET_LOAD_FACTORS:
        key_count = _key_count(target_alpha)
        present_keys = all_present_keys[:key_count]
        chaining_table = ChainedHashTable(capacity=CAPACITY)
        linear_table = LinearProbingHashTable(capacity=CAPACITY)
        for key in present_keys:
            chaining_table.put(key, key)
            linear_table.put(key, key)

        chaining_success, chaining_failure = _measure_chaining(
            chaining_table,
            present_keys,
            missing_keys,
        )
        linear_success, linear_failure = _measure_linear_probing(
            linear_table,
            present_keys,
            missing_keys,
        )
        rows.append(
            ComparisonRow(
                target_alpha=target_alpha,
                actual_alpha=key_count / CAPACITY,
                bucket_count=CAPACITY,
                key_count=key_count,
                chaining_successful_actual=chaining_success,
                chaining_successful_theory=1 + target_alpha / 2,
                chaining_unsuccessful_actual=chaining_failure,
                chaining_unsuccessful_theory=target_alpha,
                linear_successful_actual=linear_success,
                linear_successful_theory=(
                    1 + 1 / (1 - target_alpha)
                )
                / 2,
                linear_unsuccessful_actual=linear_failure,
                linear_unsuccessful_theory=(
                    1 + 1 / (1 - target_alpha) ** 2
                )
                / 2,
            )
        )
    return rows


def render_markdown_tables(rows: list[ComparisonRow]) -> str:
    sections = [
        "이론식: 체이닝 성공 1 + α/2, 실패 α; "
        "선형 탐지 성공 (1 + 1/(1-α))/2, "
        "실패 (1 + 1/(1-α)²)/2",
        "",
        "성공 탐색 평균 비교 (실측 / 이론)",
        "",
        "| 목표 α | 실측 α | 키 수 | 체이닝 | 선형 탐지 |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        sections.append(
            f"| {row.target_alpha:.1f} | {row.actual_alpha:.4f} "
            f"| {row.key_count} "
            f"| {row.chaining_successful_actual:.3f} / "
            f"{row.chaining_successful_theory:.3f} "
            f"| {row.linear_successful_actual:.3f} / "
            f"{row.linear_successful_theory:.3f} |"
        )
    sections.extend(
        (
            "",
            "실패 탐색 평균 비교 (실측 / 이론)",
            "",
            "| 목표 α | 실측 α | 키 수 | 체이닝 | 선형 탐지 |",
            "| ---: | ---: | ---: | ---: | ---: |",
        )
    )
    for row in rows:
        sections.append(
            f"| {row.target_alpha:.1f} | {row.actual_alpha:.4f} "
            f"| {row.key_count} "
            f"| {row.chaining_unsuccessful_actual:.3f} / "
            f"{row.chaining_unsuccessful_theory:.3f} "
            f"| {row.linear_unsuccessful_actual:.3f} / "
            f"{row.linear_unsuccessful_theory:.3f} |"
        )
    return "\n".join(sections)


def render_svg(rows: list[ComparisonRow], successful: bool) -> str:
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
    measurement_fields = (
        (
            "chaining_successful_actual",
            "chaining_successful_theory",
            "linear_successful_actual",
            "linear_successful_theory",
        )
        if successful
        else (
            "chaining_unsuccessful_actual",
            "chaining_unsuccessful_theory",
            "linear_unsuccessful_actual",
            "linear_unsuccessful_theory",
        )
    )
    values = [
        getattr(row, field)
        for row in rows
        for field in measurement_fields
    ]
    y_max = max(values) * 1.1

    def y_position(value: float) -> float:
        return bottom - value * (bottom - top) / y_max

    if successful:
        title = "성공 탐색 평균 비교"
        series = (
            ("체이닝 실측", "#2563eb", None, measurement_fields[0]),
            ("체이닝 이론", "#2563eb", "8 5", measurement_fields[1]),
            ("선형 탐지 실측", "#dc2626", None, measurement_fields[2]),
            ("선형 탐지 이론", "#dc2626", "8 5", measurement_fields[3]),
        )
    else:
        title = "실패 탐색 평균 비교"
        series = (
            ("체이닝 실측", "#2563eb", None, measurement_fields[0]),
            ("체이닝 이론", "#2563eb", "8 5", measurement_fields[1]),
            ("선형 탐지 실측", "#dc2626", None, measurement_fields[2]),
            ("선형 탐지 이론", "#dc2626", "8 5", measurement_fields[3]),
        )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        f"<title>{title}</title>",
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="500" y="30" text-anchor="middle" font-size="20">'
        f"{title}</text>",
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
            'text-anchor="middle" font-size="14">적재율 α</text>',
            f'<text x="22" y="{(top + bottom) / 2:.1f}" '
            'transform="rotate(-90 22 242)" text-anchor="middle" '
            'font-size="14">평균 비교 횟수</text>',
        )
    )
    for x, row in zip(x_positions, rows):
        parts.append(
            f'<text x="{x:.1f}" y="{bottom + 24}" text-anchor="middle" '
            f'font-size="12">α={row.target_alpha:.1f}</text>'
        )

    legend_positions = (110, 340, 590, 790)
    for (label, color, dash, field), legend_x in zip(
        series,
        legend_positions,
    ):
        series_values = [getattr(row, field) for row in rows]
        points = " ".join(
            f"{x:.1f},{y_position(value):.1f}"
            for x, value in zip(x_positions, series_values)
        )
        dash_attribute = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" '
            f'stroke-width="2.5"{dash_attribute}/>'
        )
        for x, value in zip(x_positions, series_values):
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


def write_outputs(
    rows: list[ComparisonRow],
    csv_path: Path,
    success_svg_path: Path,
    failure_svg_path: Path,
) -> None:
    for path in (csv_path, success_svg_path, failure_svg_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", encoding="utf-8", newline="") as result_file:
        writer = csv.writer(result_file, lineterminator="\n")
        writer.writerow(
            (
                "target_alpha",
                "actual_alpha",
                "bucket_count",
                "key_count",
                "chaining_successful_actual",
                "chaining_successful_theory",
                "chaining_unsuccessful_actual",
                "chaining_unsuccessful_theory",
                "linear_successful_actual",
                "linear_successful_theory",
                "linear_unsuccessful_actual",
                "linear_unsuccessful_theory",
            )
        )
        for row in rows:
            writer.writerow(
                (
                    f"{row.target_alpha:.1f}",
                    f"{row.actual_alpha:.6f}",
                    row.bucket_count,
                    row.key_count,
                    f"{row.chaining_successful_actual:.6f}",
                    f"{row.chaining_successful_theory:.6f}",
                    f"{row.chaining_unsuccessful_actual:.6f}",
                    f"{row.chaining_unsuccessful_theory:.6f}",
                    f"{row.linear_successful_actual:.6f}",
                    f"{row.linear_successful_theory:.6f}",
                    f"{row.linear_unsuccessful_actual:.6f}",
                    f"{row.linear_unsuccessful_theory:.6f}",
                )
            )

    success_svg_path.write_text(
        render_svg(rows, successful=True),
        encoding="utf-8",
    )
    failure_svg_path.write_text(
        render_svg(rows, successful=False),
        encoding="utf-8",
    )


def main() -> None:
    rows = run_experiment()
    csv_path = RESULTS_DIRECTORY / "compare_results.csv"
    success_svg_path = RESULTS_DIRECTORY / "compare_success.svg"
    failure_svg_path = RESULTS_DIRECTORY / "compare_failure.svg"
    write_outputs(rows, csv_path, success_svg_path, failure_svg_path)
    print(f"버킷 수: {CAPACITY}, 실패 탐색 횟수: {FAILURE_QUERY_COUNT:,}/적재율")
    print(
        "선형 탐지 실패 탐색은 이론식과 일치하도록 종료 빈 칸까지 검사 횟수에 포함합니다."
    )
    print(render_markdown_tables(rows))
    print(f"\nCSV: {csv_path.relative_to(PROJECT_ROOT)}")
    print(f"성공 그래프: {success_svg_path.relative_to(PROJECT_ROOT)}")
    print(f"실패 그래프: {failure_svg_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
