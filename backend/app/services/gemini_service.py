import json
import logging
from typing import Optional

from google import genai
from google.genai import types

from app.config import GEMINI_API_KEY, GEMINI_MODEL, GOOGLE_CLOUD_PROJECT, VERTEX_AI_LOCATION
from app.models.statement import GeminiStatementOutput

logger = logging.getLogger(__name__)

# Gemini 3 preview models require API key (Express) access rather than standard Vertex AI ADC.
# If GEMINI_API_KEY is set, use it; otherwise fall back to Vertex AI ADC (for GA models).
if GEMINI_API_KEY:
    # Vertex AI Express: API key + vertexai=True routes to the correct endpoint
    _client = genai.Client(vertexai=True, api_key=GEMINI_API_KEY)
else:
    _client = genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        location=VERTEX_AI_LOCATION,
    )

_EXTRACTION_PROMPT = """You are a financial data extraction assistant.
Extract all data from this credit card statement PDF.

Rules:
- All date fields must be in YYYY-MM-DD format.
- All amounts must be positive floats (never negative).
- debit_or_credit must be exactly "debit" or "credit".
- Include ALL transactions listed in the statement, do not skip any.
- For category, infer from the description. Use one of: Food, Travel, Shopping,
  Entertainment, Utilities, Healthcare, Fuel, EMI, Other.
- If a field is not present in the statement, use null.
- Return only valid JSON matching the required schema, no markdown fences.
"""


def extract_statement(pdf_bytes: bytes) -> Optional[GeminiStatementOutput]:
    """
    Send decrypted PDF bytes to Gemini 3 Flash and return structured statement data.
    Returns None on any failure (caller should log and mark statement as failed).
    """
    try:
        logger.info("gemini_sending_request", extra={"pdf_size_bytes": len(pdf_bytes), "model": GEMINI_MODEL})

        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                _EXTRACTION_PROMPT,
            ],
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=GeminiStatementOutput,
                thinking_config=types.ThinkingConfig(
                    thinking_level="LOW",
                ),
            ),
        )

        raw = response.text
        logger.info("gemini_extraction_success", extra={"response_length": len(raw)})

        data = json.loads(raw)
        return GeminiStatementOutput(**data)

    except json.JSONDecodeError as e:
        logger.error(
            "gemini_json_parse_failed",
            extra={"error": str(e), "raw_response": response.text[:500]},
        )
        return None
    except Exception as e:
        logger.error("gemini_extraction_failed", extra={"error": str(e)})
        return None


def generate_insights(spend_data: dict) -> str:
    """
    Generate a natural-language spending comparison narrative for the given months.
    """
    prompt = f"""You are a personal finance advisor reviewing credit card spending data.

Analyze the month-over-month changes and explain:
1. Why overall spending is higher or lower compared to previous months.
2. Which specific categories or cards drove the change.
3. Any notable patterns worth calling out.

Be specific with amounts and percentages. Keep the response under 300 words.
Write in plain text paragraphs — no markdown headers or bullet points.

Data:
{json.dumps(spend_data, indent=2)}
"""
    try:
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        logger.error("gemini_insights_failed", extra={"error": str(e)})
        return "Unable to generate insights at this time. Please try again later."
