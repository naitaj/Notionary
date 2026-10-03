from app.ai.providers.factory import get_llm_provider
from pydantic import BaseModel, Field, model_validator
from typing import List, Any, Dict

class Segment(BaseModel):
    speaker: str = Field(default="Unknown")
    topic: str = Field(default="General")
    text: str = Field(default="")

class SegmentationResult(BaseModel):
    segments: List[Segment] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"segments": data}
        if isinstance(data, dict):
            if "segments" in data:
                return data
            # Check if any list value exists in data
            for k, v in data.items():
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                    return {"segments": v}
        return data

async def run_segmentation(text: str) -> SegmentationResult:
    provider = get_llm_provider()
    sample_text = text[:4000] if len(text) > 4000 else text
    prompt = (
        "Segment the following meeting text into speaker and topic chunks. "
        "Return a JSON object with a 'segments' array of objects, each containing 'speaker', 'topic', and 'text':\n\n"
        f"{sample_text}"
    )
    system_prompt = (
        "You are an assistant that segments meeting transcripts. "
        "Output strictly valid JSON with the top-level key 'segments'."
    )
    
    try:
        return await provider.complete_structured(
            prompt=prompt,
            response_model=SegmentationResult,
            system_prompt=system_prompt,
            model="openai/gpt-oss-20b"
        )
    except Exception:
        return SegmentationResult(segments=[
            Segment(speaker="Presenter", topic="Overview", text=sample_text[:200])
        ])

