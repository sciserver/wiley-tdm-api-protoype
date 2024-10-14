# Wiley TDM Download and Extract Using Gemini

This notebook demonstrates how to download PDFs using the Wiley TDM API and
extract the text from the PDFs using the Gemini API.

To run the example, you need both a Wiley TDM API key and a Gemini API key.

You can pass the API keys as CLI arguments of set them as environment variables.

```bash
export WILEY_TDM_API_KEY=<your_wiley_tdm_api_key>
export GEMINI_API_KEY=<your_gemini_api_key>
```

To run, setup a Python environment (3.12 tested) and install the requirements:

```bash
python -m pip install -r requirements.txt
```

The run the following commands:

```bash
python -m src.download_articles --start_year 2023
python -m src.apply_gemini
python -m src.aggregate_gemini_out
```

To see more options run:

```bash
python -m src.download_articles --help
python -m src.apply_gemini --help
python -m src.aggregate_gemini_out --help
```
