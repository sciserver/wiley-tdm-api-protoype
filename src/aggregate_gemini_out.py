"""Aggregates the outputs from the gemini model."""

import csv
from pathlib import Path

import click


def main(
    output_dir: Path,
) -> None:
    """Aggregate the outputs from the gemini model."""
    outputs = list(output_dir.glob("*.txt"))

    with (output_dir / "aggregated_outputs.csv").open("w") as f:
        writer = csv.writer(f)
        # write columns
        for output in outputs:
            with open(output, "r") as f:
                # write rows
                pass


if __name__ == "__main__":
    main()
