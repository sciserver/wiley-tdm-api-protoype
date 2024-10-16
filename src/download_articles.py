"""Utility to download articles from Wiley for academic purposes.

The Wiley TDM API, as of 10/8/2024, enforces a rate limit of 3 requests per second.
With a burst of 1 request.

The list of articles to download is generated via a crossref search.

https://onlinelibrary.wiley.com/library-info/resources/text-and-datamining

Some of the code is adapted from:
https://ualibweb.github.io/UALIB_ScholarlyAPI_Cookbook/src/python/wiley-tdm.html
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import ratelimitqueue
import requests
from tqdm import tqdm

JSON = dict[str, Any]
# Notes:
# 1. The journal id is hard-coded and given, but could be changed to be a variable.
# 2. The number of rows is set to 1000, which is seems to be higher than what the
#    user would need for the given journal.
CROSSREF_QUERY_URL = "https://api.crossref.org/journals/{journal_id}/works?select=DOI,title,container-title,volume,issue,published&rows=1000&filter=from-pub-date:{start_year},until-pub-date:{end_year}"
CROSS_REF_QUERY_FAILED = "Failed to query crossref API. Status code: {response}"

WILEY_API_URL = "https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}"
WILEY_DOWNLOAD_FAILED = (
    "Failed to download article: {doi}, status code: {status_code}, response: {text}"
)
WILEY_DOWNLOAD_SUCCESS = "Successfully downloaded article: {doi}"
WILEY_DOWNLOAD_SKIP = "Skipping download of article: {doi}, already exists."
WILEY_DOWNLOAD_EXCEPTION = "Failed to download article: {doi}, exception: {e}"

MSG_N_SUCCESSFUL = "{n_successful_articles} articles downloaded successfully."
MSG_N_UNSUCCESSFUL = "{n_failed_articles} articles failed to download."

log_dir = Path(os.getcwd()) / "logs"
log_dir.mkdir(exist_ok=True)
log_file = (
    log_dir / f"download_articles_{datetime.now().strftime("%Y-%m-%d_%H:%M:%S")}.log"
)
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _doi_to_filename(doi: str) -> str:
    return doi.replace("/", "_")


def query_crossref(journal_id: int, start_year: int, end_year: int) -> JSON:
    """Query the crossref API to get a list of articles from a given journal.

    Args:
        journal_id (int): The journal ID to query.
        start_year (int): The start year of the articles to query.
        end_year (int): The end year of the articles to query.

    Returns:
        JSON: The JSON response from the crossref API.
    """
    url = CROSSREF_QUERY_URL.format(
        journal_id=journal_id, start_year=start_year, end_year=end_year
    )
    response = requests.get(url)
    if response.status_code != 200:
        logger.error(CROSS_REF_QUERY_FAILED.format(response=response.status_code))
        raise ValueError(CROSS_REF_QUERY_FAILED.format(response=response.status_code))

    return response.json()


def download_article(doi: str, out_dir: Path, api_key: str) -> bool:
    """Download an article from Wiley using the TDM API.

    Args:
        doi (str): The DOI of the article to download.
        out_dir (Path): The directory to save the article to.
        api_key (str): The API key for the Wiley TDM API.

    Returns:
        bool: True if the article was downloaded successfully, False otherwise.
    """
    response = requests.get(
        WILEY_API_URL.format(doi=doi),
        headers={"Wiley-TDM-Client-Token": api_key},
        allow_redirects=True,
    )

    if response.status_code == 200:
        with open(out_dir / f"{doi.replace("/", "_")}.pdf", "wb") as f:
            f.write(response.content)
        logger.info(WILEY_DOWNLOAD_SUCCESS.format(doi=doi))
        return True
    else:
        logger.error(
            WILEY_DOWNLOAD_FAILED.format(
                doi=doi, status_code=response.status_code, text=response.text
            )
        )
        return False


def _set_default_end_year(ctx, _, value):
    """Helper function to set the default end year."""
    if value is None:
        return ctx.params["start_year"]
    return value


@click.command()
@click.option(
    "--out_dir",
    type=click.Path(file_okay=False, readable=True, writable=True, path_type=Path),
    default=Path(os.getcwd()) / "articles",
)
@click.option("--journal_id", type=int, default=10808620)
@click.option("--start_year", type=int, required=True)
@click.option("--end_year", type=int, default=None, callback=_set_default_end_year)
@click.option("--api_key", type=str, envvar="WILEY_API_KEY")
@click.option("--save_crossref_out", is_flag=True)
@click.option("--rlq_calls", type=int, default=2)
@click.option("--rlq_per_second", type=int, default=1)
def main(
    out_dir: Path,
    journal_id: int,
    start_year: int,
    end_year: int,
    api_key: str,
    save_crossref_out: bool,
    rlq_calls: int,
    rlq_per_second: int,
) -> None:
    """Download articles from Wiley for academic purposes.

    Args:
        out_dir (Path): The directory to save the articles to.
        journal_id (int): The journal ID to query.
        start_year (int): The start year of the articles to query.
        end_year (int): The end year of the articles to query.
        api_key (str): The API key for the Wiley TDM API.
        save_crossref_out (bool): Whether to save the crossref output to a file.
        rlq_calls (int): The number of calls to make per second.
        rlq_per_second (int): The number of seconds to make calls for.

    Returns:
        None
    """

    out_dir.mkdir(exist_ok=True)

    articles = query_crossref(journal_id, start_year, end_year)

    if save_crossref_out:
        with open(out_dir / "crossref_articles.json", "w") as f:
            json.dump(articles, f, indent=2)

    columns = ["DOI", "title", "container-title", "volume", "issue", "published"]
    with open(out_dir / f"articles_{journal_id}_{start_year}_{end_year}.tsv", "w") as f:
        f.write("\t".join(columns) + "\n")
        for article in articles["message"]["items"]:
            if article.get("title", None):
                f.write(f"{article['DOI']}\t")
                for c in columns[1:3]:
                    f.write(f"{article.get(c, [""])[0]}\t")
                for c in columns[3:-1]:
                    f.write(f"{article.get(c, "")}\t")
                f.write(
                    f"{"-".join(map(str, article['published']["date-parts"][0]))}\n"
                )

    dois = [
        article["DOI"]
        for article in articles["message"]["items"]
        if article.get("title", None)
    ]

    dois_to_download = ratelimitqueue.RateLimitQueue(
        calls=rlq_calls, per=rlq_per_second
    )
    for doi in dois:
        if not (out_dir / f"{_doi_to_filename(doi)}.pdf").exists():
            dois_to_download.put(doi)
        else:
            logger.info(WILEY_DOWNLOAD_SKIP.format(doi=doi))

    pbar = tqdm(total=dois_to_download.qsize())
    results = []
    while not dois_to_download.empty():
        doi = dois_to_download.get()
        try:
            results.append(download_article(doi=doi, out_dir=out_dir, api_key=api_key))
        except Exception as e:
            logger.error(WILEY_DOWNLOAD_EXCEPTION.format(doi=doi, e=e))

        pbar.update()
        dois_to_download.task_done()

    n_successful_articles = sum(results)
    n_failed_articles = len(results) - n_successful_articles

    print(MSG_N_SUCCESSFUL.format(n_successful_articles=n_successful_articles))
    if n_failed_articles:
        print(MSG_N_UNSUCCESSFUL.format(n_failed_articles=n_failed_articles))


if __name__ == "__main__":
    main()
