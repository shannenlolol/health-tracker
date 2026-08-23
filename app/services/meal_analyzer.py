import base64

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import settings


class MealEstimate(BaseModel):
    description: str = Field(description="Short, familiar name for the complete meal")
    estimated_calories: int = Field(ge=0, le=5000)
    protein_g: float = Field(ge=0, le=500)
    carbs_g: float = Field(ge=0, le=1000)
    fat_g: float = Field(ge=0, le=500)


SYSTEM_PROMPT = """You estimate nutrition for an older Singaporean adult's food log.
Return one practical estimate for the whole meal. Recognize local foods and portions.
Do not give medical advice. If portions are unclear, use a typical hawker/restaurant serving.
Keep the description plain and under 80 characters. Round calories to the nearest 10 and
macros to whole grams."""


class MealAnalyzer:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def from_text(self, description: str) -> MealEstimate:
        response = await self.client.responses.parse(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Estimate this meal: {description}"},
            ],
            text_format=MealEstimate,
        )
        return response.output_parsed

    async def from_image(self, image: bytes, mime_type: str, caption: str = "") -> MealEstimate:
        encoded = base64.b64encode(image).decode("ascii")
        response = await self.client.responses.parse(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": f"Estimate the meal in this photo. Note: {caption or 'none'}"},
                        {"type": "input_image", "image_url": f"data:{mime_type};base64,{encoded}"},
                    ],
                },
            ],
            text_format=MealEstimate,
        )
        return response.output_parsed
