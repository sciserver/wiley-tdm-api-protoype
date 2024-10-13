"""Aggregates the outputs from the gemini model."""

import csv
import functools
import string
from pathlib import Path

import click
from tqdm import tqdm

all_letters_and_digits = set(string.ascii_letters + string.digits)


def process_lines(lines: list[str]) -> list[str]:
    """Process the lines from the gemini model."""
    rejection_criteria = [
        lambda line: line.startswith("```"),  # gemini wraps a csv with ticks
        lambda line: (set(line) ^ all_letters_and_digits)
        == 0,  # line doesn't have any letters or digits
    ]

    def rejection_f(x: str) -> bool:
        for criteria in rejection_criteria:
            if criteria(x):
                return True
        return False

    for line in lines:
        print(rejection_f(line), line)

    return [line.strip() for line in lines if not rejection_f(line)]


@click.command()
@click.option("--out_dir", type=click.Path(path_type=Path), default=Path("outputs"))
def main(
    out_dir: Path,
) -> None:
    """Aggregate the outputs from the gemini model."""
    outputs = list(out_dir.glob("*.txt"))

    with (out_dir / "aggregated_outputs.csv").open("w") as f:
        writer = csv.writer(f)
        columns = ["doi"]
        for output in tqdm(outputs, desc="Aggregating outputs"):
            with output.open() as f:
                lines = process_lines(f.readlines())
                print(lines)
                if not lines:
                    continue
                if len(columns) == 1:
                    columns += lines[0].split(",")
                    writer.writerow(columns)
                for line in lines[1:]:
                    writer.writerow([output.stem] + line.split(","))


if __name__ == "__main__":
    main()
