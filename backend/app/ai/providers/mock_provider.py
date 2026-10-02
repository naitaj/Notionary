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
    ) -> T:
        # Build a safe default structure according to the requested model
        model_name = response_model.__name__
        if model_name == "ExtractionResult":
            return response_model.model_validate({
                "schema_version": "1.0.0",
                "document_id": "doc_mock_m04",
                "doc_type": "meeting_note",
                "decisions": [{
                    "code": "D-17",
                    "statement": "Adopt MobileNetV3-Small as the edge inference architecture for on-device deployment.",
                    "rationale": "Selected because latency is 14.2ms vs 31.8ms for Model A while achieving 88.2% F1 score.",
                    "alternatives": [{"name": "Model A (ResNet-18)", "reason": "Exceeded 20ms edge latency budget"}],
                    "decided_by_alias": "Karan Mehta",
                    "decided_date_str": "2026-03-15",
                    "excerpt": "Karan: 'Let's lock in MobileNetV3-Small for the on-device pipeline.'",
                }],
                "tasks": [{
                    "code": "T-14",
                    "title": "Quantize MobileNetV3-Small to INT8 via TensorRT-LLM",
                    "owner_alias": "Ananya",
                    "due_date_str": "2026-03-25",
                    "priority": "high",
                    "origin_decision_code": "D-17",
                    "excerpt": "Ananya: 'I will take the quantization task and deliver benchmarks by next Wednesday.'",
                }],
                "experiments": [{
                    "code": "EXP-06",
                    "hypothesis": "MobileNetV3-Small achieves >85% F1 within 20ms latency",
                    "model": "MobileNetV3-Small",
                    "dataset": "LeafSet-v1",
                    "parameters": {"batch_size": 1, "precision": "FP16"},
                    "owner_alias": "Karan Mehta",
                    "metric": "latency",
                    "metric_value": 14.2,
                    "metric_unit": "ms",
                    "excerpt": "Benchmarked MobileNetV3-Small on Jetson Nano: 14.2ms latency, 88.2% F1.",
                }],
                "claims": [{
                    "statement": "MobileNetV3-Small is robust across lighting conditions with 88.2% F1 score.",
                    "claim_type": "observation",
                    "subject": "MobileNetV3-Small",
                    "metric": "f1_score",
                    "direction": "increase",
                    "dataset": "LeafSet-v1",
                    "value": 88.2,
                    "excerpt": "Field trials show 88.2% F1 accuracy on LeafSet-v1.",
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
