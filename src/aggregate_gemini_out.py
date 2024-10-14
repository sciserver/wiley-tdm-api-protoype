"""Aggregates the outputs from the gemini model."""

import csv
import logging
import os
import string
from datetime import datetime
from pathlib import Path

import click
from tqdm import tqdm

log_dir = Path(os.getcwd()) / "logs"
log_dir.mkdir(exist_ok=True)
log_file = (
    log_dir / f"aggregate_gemini_{datetime.now().strftime("%Y-%m-%d_%H:%M:%S")}.log"
)
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ALL_LETTERS_AND_DIGITS = set(string.ascii_letters + string.digits)
MSG_AGGREGRATING_FILE = "Aggregating outputs from {output}"


def process_lines(lines: list[str]) -> list[str]:
    """Process the lines from the gemini model."""
    rejection_criteria = [
        # gemini wraps a csv with ticks
        lambda line: line.startswith("```"),
        # line doesn't have any letters or digits
        lambda line: (set(line) ^ ALL_LETTERS_AND_DIGITS) == 0,
    ]

    def rejection_f(x: str) -> bool:
        for criteria in rejection_criteria:
            if criteria(x):
                return True
        return False

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
            logger.info(MSG_AGGREGRATING_FILE.format(output=output))
            with output.open() as f:
                if lines := process_lines(f.readlines()):
                    if len(columns) == 1:
                        columns += lines[0].split(",")
                        writer.writerow(columns)
                    for line in lines[1:]:
                        writer.writerow([output.stem] + line.split(","))


if __name__ == "__main__":
    main()
