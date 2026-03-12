# Kaggle Dataset Integration

This document explains how the Kaggle IMDB dataset search integration works.

## Overview

The search engine now checks the Kaggle IMDB dataset **before** calling the Tavily API. If the dataset returns results that are highly correlated with the user's query, it uses those results instead of making an API call.

## How It Works

1. **Query Processing**: When a search is performed, the system first checks the Kaggle IMDB dataset
2. **Correlation Check**: It calculates a correlation score (0.0 to 1.0) between the query and dataset entries
3. **Threshold Decision**: If the correlation score is >= the threshold (default: 0.7), it uses Kaggle results
4. **Fallback**: If correlation is below threshold, it proceeds to Tavily API search as before

## Configuration

You can configure the Kaggle integration via environment variables:

```bash
# Enable/disable Kaggle search (default: true)
ENABLE_KAGGLE_SEARCH=true

# Correlation threshold (0.0-1.0, default: 0.7)
# Higher values = stricter matching (only very relevant results)
# Lower values = more lenient matching (more results from Kaggle)
KAGGLE_CORRELATION_THRESHOLD=0.7

# Optional: specific dataset file path
KAGGLE_DATASET_PATH=""
```

## Dataset

The integration uses the IMDB dataset from Kaggle:
- **Dataset**: `parthdande/imdb-dataset-2024-updated`
- **Auto-loads**: The dataset is automatically loaded on first use and cached in memory
- **Format**: Pandas DataFrame

## Correlation Scoring

The correlation algorithm checks for:
- **Movie titles** (high weight: 0.4)
- **Person names** (actors, directors) (medium weight: 0.3)
- **Keywords** (director, released, cast, etc.) (low weight: 0.1)
- **General term matching** (fallback)

## Example Usage

The integration is automatic - no code changes needed in your queries:

```python
from src.cinemind.agent import CineMind

agent = CineMind()

# This will automatically:
# 1. Check Kaggle dataset first
# 2. Use Kaggle if correlation >= 0.7
# 3. Fall back to Tavily API if not
result = await agent.search_and_analyze("Who directed The Matrix?")
```

## Installation

Make sure you have the required dependency:

```bash
pip install kagglehub[pandas-datasets]
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Notes

- The dataset is loaded once and cached in memory for performance
- Kaggle search runs in a thread pool to avoid blocking the async event loop
- If Kaggle dataset is unavailable, the system automatically falls back to Tavily
- Results from Kaggle include a `correlation` score and `source: "kaggle_imdb"`

