import hashlib
import json
import math
from typing import Optional, Type, TypeVar, List
from pydantic import BaseModel
from app.ai.providers.base import LLMProvider, EmbeddingProvider

T = TypeVar("T", bound=BaseModel)

class MockLLMProvider(LLMProvider):
    """Deterministic mock provider delivering demo responses without external network/token cost."""
    
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        **kwargs,
    ) -> str:
        if "Why was Model B chosen" in prompt or "lineage" in prompt.lower():
            return (
                "Model B (MobileNetV3-Small) was selected in decision D-17 because experiment EXP-06 "
                "demonstrated 88.2% F1 score at 14.2ms latency, meeting the strict edge latency budget "
                "defined in R-02 and outperforming Model A on battery constraints."
            )
        return "Notionary Project Intelligence: Automated reasoning completed successfully."

    async def complete_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> T:
        # Build a safe default structure according to the requested model
        model_name = response_model.__name__
        if model_name == "SegmentationResult":
            return response_model.model_validate({
                "segments": [
                    {
                        "speaker": "Karan Mehta",
                        "topic": "Architecture Review",
                        "text": prompt[:200] if len(prompt) > 200 else prompt
                    }
                ]
            })
        if model_name == "ExtractionResult":
            return response_model.model_validate({
                "schema_version": "1.0.0",
                "document_id": "doc_mock_m04",
                "doc_type": "meeting_note",
                "decisions": [{
                    "code": "D-17",
                    "statement": "Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.",
                    "rationale": "MobileNetV3-Small meets our strict 20ms edge latency ceiling (clocking 14.2ms) while maintaining high accuracy (88.2% F1 score), whereas Model A (ResNet-18) exceeded 31ms latency and consumed twice the battery power.",
                    "alternatives": [{"name": "Model A (ResNet-18)", "reason": "Exceeded 20ms edge latency budget"}],
                    "decided_by_alias": "Karan Mehta",
                    "decided_date_str": "2026-03-15",
                    "excerpt": "Decision D-17: Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.",
                }],
                "tasks": [{
                    "code": "T-14",
                    "title": "Quantize MobileNetV3-Small to INT8 via TensorRT-LLM",
                    "owner_alias": "Ananya Patel",
                    "due_date_str": "2026-03-25",
                    "priority": "high",
                    "origin_decision_code": "D-17",
                    "excerpt": "Ananya Patel: Agreed. I will take on task T-14: Quantize MobileNetV3-Small to INT8 via TensorRT-LLM and evaluate accuracy drop by March 25.",
                }],
                "experiments": [{
                    "code": "EXP-06",
                    "hypothesis": "MobileNetV3-Small achieves 88.2% F1 within 20ms latency",
                    "model": "MobileNetV3-Small",
                    "dataset": "PlantVillage Clean v2",
                    "parameters": {"batch_size": 1, "precision": "FP16"},
                    "owner_alias": "Ananya Patel",
                    "metric": "latency",
                    "metric_value": 14.2,
                    "metric_unit": "ms",
                    "excerpt": "MobileNetV3-Small achieves 88.2% F1 accuracy on the PlantVillage Clean v2 dataset with an average inference latency of 14.2ms on the Jetson Nano target board.",
                }],
                "claims": [{
                    "statement": "ResNet-18 clocked in at 31.8ms, violating thermal and battery constraints",
                    "claim_type": "observation",
                    "subject": "ResNet-18",
                    "metric": "latency",
                    "direction": "increase",
                    "dataset": "PlantVillage Clean v2",
                    "value": 31.8,
                    "excerpt": "ResNet-18 clocked in at 31.8ms, which violates our thermal and battery constraints for continuous handheld scanning.",
                }],
                "discarded_excerpts_count": 0,
            })
        
        # Fallback default instantiation
        return response_model.model_validate({})

class LocalEmbeddingProvider(EmbeddingProvider):
    """Generates deterministic, normalized 384-dimensional vectors using SHA-256 seed projection."""
    
    @property
    def dimension(self) -> int:
        return 384

    def _hash_to_vector(self, text: str) -> List[float]:
        # Hash text into deterministic pseudo-random floats, normalized to unit length
        vector = []
        base_hash = hashlib.sha256(text.encode("utf-8")).digest()
        for i in range(self.dimension):
            h = hashlib.sha256(base_hash + i.to_bytes(2, "big")).digest()
            val = (int.from_bytes(h[:4], "big") / 0xFFFFFFFF) * 2.0 - 1.0
            vector.append(val)
        
        # Normalize
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [round(x / norm, 5) for x in vector]

    async def embed_text(self, text: str) -> List[float]:
        return self._hash_to_vector(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_to_vector(t) for t in texts]
