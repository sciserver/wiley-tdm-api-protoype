"""Sample script to apply gemini to a file."""

from pathlib import Path

import click
import google.generativeai as genai
import pandas as pd
import PyPDF2

DEFAULT_PROMPT = (
    "Create a table describing the datasets used in the above text with"
    " the following fields: dataset name, years covered, article title, all"
    " article authors (with a separate column for each author)."
)


def process_pdf(model: genai.types.Model, file_path: Path, prompt: str) -> str:
    # open the pdf and pasrse pdf
    # taken from google gemini exmaple docs
    with open(file_path, "rb") as file:
        pdf = PyPDF2.PdfReader(file)
        doc_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                doc_text += text

    return model.generate_content([doc_text, prompt]).text


@click.command()
@click.option("--model_name", default="gemini-1.5-flash")
@click.option(
    "--articles_dir", type=click.Path(path_type=Path), default=Path("articles")
)
@click.option("--prompt", default=DEFAULT_PROMPT)
@click.option("--api_key", type=str, envvar="GEMINI_API_KEY")
def main(model_name: str, articles_dir: Path, prompt: str, api_key: str) -> None:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=model_name)
    aricle_metadata = pd.read_csv(
        articles_dir / "articles_10808620_2023_2023.tsv", sep="\t"
    )

    article_path = articles_dir / "10.1111_1540-6229.12423.pdf"
    generated_text = process_pdf(model, article_path, prompt)

    print(generated_text)


if __name__ == "__main__":
    main()
