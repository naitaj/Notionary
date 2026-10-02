from app.ai.providers.factory import get_llm_provider
from pydantic import BaseModel, Field
from typing import List

class Segment(BaseModel):
    speaker: str = Field(default="Unknown")
    topic: str
    text: str

class SegmentationResult(BaseModel):
    segments: List[Segment]

async def run_segmentation(text: str) -> SegmentationResult:
    provider = get_llm_provider()
    prompt = f"Segment the following meeting text into speaker and topic chunks:\n\n{text}"
    system_prompt = "You are an assistant that segments meeting transcripts."
    
    return await provider.complete_structured(
        prompt=prompt,
        response_model=SegmentationResult,
        system_prompt=system_prompt,
        model="llama-3.1-8b-instant"
    )
