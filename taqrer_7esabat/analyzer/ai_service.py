"""
Claude API Reasoning Service for Data Analysis Engine.

Handles communications with the Anthropic Messages API using:
- Pinned Model: claude-3-5-sonnet-20241022
- Explicit max_tokens: 8000
- Explicit timeout: 30 seconds
- Strict Pydantic Schema Validation
- Full-dataset statistical profiling
- In-memory / file hash caching
"""

import os
import json
import hashlib
import logging
import requests
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Pinned API Settings
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
MAX_TOKENS = 8000
API_TIMEOUT_SECONDS = 30


# ---------------------------------------------------------
# Pydantic Schemas for Strict JSON Validation
# ---------------------------------------------------------

class DerivedMetric(BaseModel):
    name: str
    formula_description: Optional[str] = ""
    columns_used: List[str] = Field(default_factory=list)


class RecommendedKPI(BaseModel):
    label: str
    value_description: Optional[str] = ""
    columns_used: List[str] = Field(default_factory=list)
    operation: Optional[str] = "sum"  # sum, mean, count, max, min, ratio
    target_column: Optional[str] = ""


class RecommendedChart(BaseModel):
    type: str  # bar, line, pie, scatter, doughnut
    title: str
    x: Optional[str] = ""
    y: Optional[str] = ""
    reason: Optional[str] = ""
    aggregation: Optional[str] = "sum"  # sum, mean, count


class DataQualityFlag(BaseModel):
    issue: str
    columns: List[str] = Field(default_factory=list)
    severity: Optional[str] = "medium"  # low, medium, high


class RequestedItemChecklist(BaseModel):
    request_item: str
    fulfilled: bool
    how: Optional[str] = ""


class AIAnalysisResponse(BaseModel):
    column_roles: Dict[str, str] = Field(default_factory=dict)
    derived_metrics: List[DerivedMetric] = Field(default_factory=list)
    recommended_kpis: List[RecommendedKPI] = Field(default_factory=list)
    recommended_charts: List[RecommendedChart] = Field(default_factory=list)
    key_insights: List[str] = Field(default_factory=list)
    data_quality_flags: List[DataQualityFlag] = Field(default_factory=list)
    requested_items_checklist: List[RequestedItemChecklist] = Field(default_factory=list)


# ---------------------------------------------------------
# AI Service Class
# ---------------------------------------------------------

class AIService:
    """Service to generate data analysis recommendations using Claude API."""

    _cache: Dict[str, Dict[str, Any]] = {}

    SYSTEM_PROMPT = """You are an expert lead data analyst and business intelligence engineer.
Analyze the provided dataset profile and user request to recommend an optimal, custom-tailored analysis plan.

HARD RULES YOU MUST FOLLOW AT ALL COSTS:
1. NEVER aggregate (sum, average, min, max) an `identifier` column (such as IDs, Student IDs, reference codes, phone numbers, zip codes). Identifier columns must ONLY be counted or used as grouping dimensions.
2. Every "highest/lowest X" claim or KPI statement MUST explicitly name the exact metric it is based on (e.g. "highest-absence subject: Biology, based on total absence days") — never output a bare number or label with no stated basis.
3. Revenue-like totals MUST use the correct formula (price × quantity) whenever both price and quantity columns are present in the dataset.
4. Classify every single column's role into one of ("identifier", "measure", "dimension", "date", "text") BEFORE deciding any calculation or chart.
5. IF A CUSTOM USER REQUEST IS PROVIDED (in Arabic or English):
   - Parse the user's custom request into a discrete list of items in `requested_items_checklist`.
   - For EVERY SINGLE ITEM in that checklist, evaluate if the data supports it.
   - Set `fulfilled: true` with an explanation of how it is addressed, OR `fulfilled: false` with a clear reason (e.g. "No date column found in dataset"). Do not omit any requested items.

Return ONLY a strict, raw JSON object matching the requested schema. No prose, no markdown code blocks, no trailing comments.

JSON Schema format required:
{
  "column_roles": { "column_name": "identifier | measure | dimension | date | text" },
  "derived_metrics": [ { "name": "...", "formula_description": "...", "columns_used": ["..."] } ],
  "recommended_kpis": [ { "label": "...", "value_description": "...", "columns_used": ["..."], "operation": "sum|mean|count|max|min", "target_column": "..." } ],
  "recommended_charts": [ { "type": "bar|line|pie|scatter|doughnut", "title": "...", "x": "...", "y": "...", "reason": "...", "aggregation": "sum|mean|count" } ],
  "key_insights": [ "..." ],
  "data_quality_flags": [ { "issue": "...", "columns": ["..."], "severity": "low|medium|high" } ],
  "requested_items_checklist": [ { "request_item": "...", "fulfilled": true, "how": "..." } ]
}"""

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        """Retrieve Anthropic API key from environment or Django settings."""
        key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        if not key:
            try:
                from django.conf import settings
                key = getattr(settings, "ANTHROPIC_API_KEY", None) or getattr(settings, "CLAUDE_API_KEY", None)
            except Exception:
                pass
        return key

    @classmethod
    def analyze_dataset(cls, df, custom_query: str = "") -> Optional[Dict[str, Any]]:
        """
        Analyze dataset by sending dataset profile and sample rows to Claude API.
        Returns parsed and validated response dict, or None on failure/fallback.
        """
        # Build statistical profile over FULL dataset
        full_stats = cls._build_full_dataset_profile(df)
        
        # Take 15-30 representative rows for context
        sample_rows = cls._extract_sample_rows(df, sample_size=25)

        # Build cache key
        cache_str = json.dumps(full_stats, sort_keys=True) + f"||{custom_query}"
        cache_key = hashlib.md5(cache_str.encode('utf-8')).hexdigest()
        
        if cache_key in cls._cache:
            logger.info("Returning cached Claude API response.")
            return cls._cache[cache_key]

        api_key = cls.get_api_key()
        if not api_key:
            logger.warning("No Anthropic API key found. Falling back to local analysis.")
            return None

        prompt_payload = {
            "dataset_info": {
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "columns_and_full_statistics": full_stats,
            },
            "sample_rows_for_context": sample_rows,
            "custom_user_request": custom_query.strip() if custom_query else None
        }

        user_message_text = f"Here is the dataset profile and sample rows:\n\n{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}"

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        request_body = {
            "model": CLAUDE_MODEL,
            "max_tokens": MAX_TOKENS,
            "system": cls.SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": user_message_text}
            ]
        }

        try:
            logger.info(f"Calling Claude API ({CLAUDE_MODEL}) with timeout={API_TIMEOUT_SECONDS}s...")
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                json=request_body,
                headers=headers,
                timeout=API_TIMEOUT_SECONDS
            )

            if response.status_code != 200:
                logger.error(f"Claude API HTTP Error {response.status_code}: {response.text}")
                return None

            resp_json = response.json()
            content_blocks = resp_json.get("content", [])
            if not content_blocks:
                logger.error("Claude API returned empty response content.")
                return None

            raw_text = content_blocks[0].get("text", "").strip()
            logger.debug(f"Raw API Response: {raw_text}")

            # Strip markdown code blocks if present
            clean_text = raw_text
            if clean_text.startswith("```"):
                clean_text = clean_text.split("\n", 1)[-1]
                if clean_text.endswith("```"):
                    clean_text = clean_text.rsplit("```", 1)[0]
                clean_text = clean_text.replace("```json", "").replace("```", "").strip()

            parsed_dict = json.loads(clean_text)

            # Validate against Pydantic schema
            validated = AIAnalysisResponse.model_validate(parsed_dict)
            result_dict = validated.model_dump()

            # Store in cache
            cls._cache[cache_key] = result_dict
            return result_dict

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude API response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            return None

    @classmethod
    def _build_full_dataset_profile(cls, df) -> Dict[str, Any]:
        """Compute per-column statistics over the FULL dataset."""
        import numpy as np
        stats = {}
        total_rows = len(df)

        for col in df.columns:
            series = df[col]
            non_null = series.dropna()
            missing_count = int(series.isnull().sum())
            missing_pct = round(missing_count / total_rows * 100, 1) if total_rows > 0 else 0
            n_unique = int(non_null.nunique())

            col_stat = {
                "dtype": str(series.dtype),
                "total_non_null": len(non_null),
                "missing_count": missing_count,
                "missing_pct": missing_pct,
                "unique_count": n_unique,
            }

            # Check if numeric
            if pd.api.types.is_numeric_dtype(series):
                if len(non_null) > 0:
                    col_stat["min"] = float(non_null.min())
                    col_stat["max"] = float(non_null.max())
                    col_stat["mean"] = float(non_null.mean())
                    col_stat["std"] = float(non_null.std()) if len(non_null) > 1 else 0.0
            else:
                # Top frequent sample values
                top_vals = non_null.value_counts().head(5).to_dict()
                col_stat["top_frequent_values"] = {str(k): int(v) for k, v in top_vals.items()}

            stats[str(col)] = col_stat

        return stats

    @classmethod
    def _extract_sample_rows(cls, df, sample_size: int = 25) -> List[Dict[str, Any]]:
        """Extract a sample of rows formatted as dictionaries."""
        if len(df) <= sample_size:
            sample_df = df
        else:
            # Pick evenly spaced rows for representative sample
            indices = list(range(0, len(df), max(1, len(df) // sample_size)))[:sample_size]
            sample_df = df.iloc[indices]

        # Convert datetimes and numpy types to serializable format
        clean_rows = []
        for idx, row in sample_df.iterrows():
            clean_row = {}
            for col in sample_df.columns:
                val = row[col]
                if hasattr(val, 'isoformat'):
                    val = val.isoformat()
                elif hasattr(val, 'item'):
                    val = val.item()
                elif str(val) == 'nan' or str(val) == 'None':
                    val = None
                clean_row[str(col)] = val
            clean_rows.append(clean_row)
        return clean_rows
