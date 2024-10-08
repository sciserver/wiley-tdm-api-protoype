"""Utility to download articles from Wiley for academic purposes.

The Wiley TDM API, as of 10/8/2024, enforces a rate limit of 3 reuqests per second.
With a burst of 1 request.

The list of articles to download is generated via a crossref search.

https://onlinelibrary.wiley.com/library-info/resources/text-and-datamining

Some of the code is adapted from:
https://ualibweb.github.io/UALIB_ScholarlyAPI_Cookbook/src/python/wiley-tdm.html
"""

import functools
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import pyrate_limiter as pyr
import requests
from tqdm.contrib import concurrent

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

limiter = pyr.Limiter(
    pyr.Rate(1, pyr.Duration.SECOND), raise_when_fail=False, max_delay=100_000
)

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

    try:
        limiter.try_acquire(doi)
    except pyr.TooManyRequests:
        logger.error(f"Rate limit exceeded for article: {doi}")
        return False

    response = requests.get(
        WILEY_API_URL.format(doi=doi),
        headers={"Wiley-TDM-Client-Token": api_key},
        allow_redirects=True,
    )

    if response.status_code == 200:
        with open(out_dir / f"{doi.replace("/", "_")}.pdf", "wb") as f:
            f.write(response.content)
        logger.info(f"Successfully downloaded article: {doi}")
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
def main(
    out_dir: Path,
    journal_id: int,
    start_year: int,
    end_year: int,
    api_key: str,
    save_crossref_out: bool,
) -> None:
    out_dir.mkdir(exist_ok=True)

    articles = query_crossref(journal_id, start_year, end_year)

    if save_crossref_out:
        with open(out_dir / "crossref_articles.json", "w") as f:
            json.dump(articles, f, indent=2)

    dois = [
        article["DOI"]
        for article in articles["message"]["items"]
        if article.get("title", None)
    ]

    dois_to_download = []
    for doi in dois:
        if not (out_dir / f"{_doi_to_filename(doi)}.pdf").exists():
            dois_to_download.append(doi)
        else:
            logger.info(f"Skipping download of article: {doi}, already exists.")

    download_f = functools.partial(download_article, out_dir=out_dir, api_key=api_key)
    # Note: The max_workers is set to 1 to avoid hitting the burst limit of the Wiley API.
    results = concurrent.process_map(download_f, dois_to_download, max_workers=1)
    n_successful_articles = sum(results)
    n_failed_articles = len(dois_to_download) - n_successful_articles

    print(f"Downloaded {n_successful_articles} articles.")
    if n_failed_articles:
        print(
            f"{n_failed_articles} articles failed to download. Check the log file for more information."
        )


if __name__ == "__main__":
    main()
