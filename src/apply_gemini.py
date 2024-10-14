"""Sample script to apply gemini to a file."""

import logging
import os
from datetime import datetime
from pathlib import Path

import click
import google.generativeai as genai
import PyPDF2
import ratelimitqueue
from tqdm import tqdm

DEFAULT_PROMPT = (
    "Create a csv describing the datasets used in the above text with"
    " the following fields: dataset name, years covered, article title, all"
    " article authors (with a separate column for each author)."
)

ERR_MSG = "Error processing {article}: {e}"
SUCCESS_MSG = "Successfully processed {article}"

log_dir = Path(os.getcwd()) / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"apply_gemini_{datetime.now().strftime("%Y-%m-%d_%H:%M:%S")}.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def process_pdf(model: genai.types.Model, file_path: Path, prompt: str) -> str:
    """Process a PDF file using the given model and prompt.

    Args:

        model (genai.types.Model): The model to use for processing.
        file_path (Path): The path to the PDF file to process.
        prompt (str): The prompt to use for processing.

        Returns:
            str: The generated text.
    """
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
@click.option("--rlq_calls", type=int, default=10)
@click.option("--rlq_per_second", type=int, default=60)
def main(
    model_name: str,
    articles_dir: Path,
    out_dir: Path,
    prompt: str,
    api_key: str,
    rlq_calls: int,
    rlq_per_second: int,
) -> None:
    """Apply the Gemini model to a set of PDF files.

    Args:
        model_name (str): The name of the model to use.
        articles_dir (Path): The directory containing the PDF files to process.
        out_dir (Path): The directory to save the generated text to.
        prompt (str): The prompt to use for generating text.
        api_key (str): The API key for the Gemini API.
        rlq_calls (int): The number of calls allowed per second.
        rlq_per_second (int): The number of seconds to make calls for.
    """
    if not out_dir.exists():
        out_dir.mkdir()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=model_name)

    articles_in_dir = list(articles_dir.iterdir())
    articles = list(
        filter(
            lambda fname: not (out_dir / f"{fname.stem}.txt").exists()
            and fname.suffix == ".pdf",
            articles_in_dir,
        )
    )
    logger.info(f"Found {len(articles_in_dir)} articles.")
    logger.info(f"{len(articles)} articles need to be processed.")

    article_queue = ratelimitqueue.RateLimitQueue(calls=rlq_calls, per=rlq_per_second)
    for article in articles:
        article_queue.put(article)

    pbar = tqdm(total=article_queue.qsize())
    while not article_queue.empty():
        article = article_queue.get()
        output_loc = out_dir / f"{article.stem}.txt"
        try:
            generated_text = process_pdf(model, article, prompt)
        except Exception as e:
            logger.error(ERR_MSG.format(article=article, e=e))
            pbar.update()
            continue

        with output_loc.open("w") as f:
            f.write(generated_text)
        pbar.update()
        article_queue.task_done()
        logger.info(SUCCESS_MSG.format(article=article))


if __name__ == "__main__":
    main()
