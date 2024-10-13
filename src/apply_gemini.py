"""Sample script to apply gemini to a file."""

from pathlib import Path

import click
import google.generativeai as genai
import pandas as pd
import PyPDF2
import ratelimitqueue
from tqdm import tqdm

DEFAULT_PROMPT = (
    "Create a csv describing the datasets used in the above text with"
    " the following fields: dataset name, years covered, article title, all"
    " article authors (with a separate column for each author)."
)


def process_pdf(model: genai.types.Model, file_path: Path, prompt: str) -> str:
    # open the pdf and parse pdf
    # taken from google gemini example docs
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
@click.option("--out_dir", type=click.Path(path_type=Path), default=Path("outputs"))
@click.option("--prompt", default=DEFAULT_PROMPT)
@click.option("--api_key", type=str, envvar="GEMINI_API_KEY")
def main(
    model_name: str, articles_dir: Path, out_dir: Path, prompt: str, api_key: str
) -> None:
    if not out_dir.exists():
        out_dir.mkdir()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=model_name)

    articles = filter(
        lambda fname: not (out_dir / f"{fname.stem}.txt").exists()
        and fname.suffix == ".pdf",
        list(articles_dir.iterdir()),
    )

    article_queue = ratelimitqueue.RateLimitQueue(calls=10, per=60)
    for article in articles:
        article_queue.put(article)

    pbar = tqdm(total=article_queue.qsize())
    while not article_queue.empty():
        article = article_queue.get()
        output_loc = out_dir / f"{article.stem}.txt"
        try:
            generated_text = process_pdf(model, article, prompt)
        except Exception as e:
            print(f"Error processing {article}: {e}")
            pbar.update()
            continue

        with output_loc.open("w") as f:
            f.write(generated_text)
        pbar.update()
        article_queue.task_done()


if __name__ == "__main__":
    main()
