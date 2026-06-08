from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Dict
import uuid
import math


DEFAULT_SCARCITY_WEIGHTS: Dict[str, float] = {
    "water":   1.8,
    "food":    1.5,
    "energy":  1.2,
    "shelter": 1.4,
    "default": 1.0,
}


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    api_key_secret: str = "changeme"
    database_url: str = "sqlite:///./pulsermesh.db"
    node_id: str = str(uuid.uuid4())

    # Node's reference OaZaTa position on the mesh.
    # Za is the critical value — it defines the node's phase reference.
    # Steward proximity is computed relative to this.
    # Default: Oa=1.0 (unit thickness), Za=0.0 (reference phase), Ta=0.0 (origin)
    node_oa: float = 1.0
    node_za: float = 0.0
    node_ta: float = 0.0

    # JSON string override for scarcity weights
    scarcity_weights_json: str = ""

    def scarcity_weights(self) -> Dict[str, float]:
        if self.scarcity_weights_json:
            import json
            overrides = json.loads(self.scarcity_weights_json)
            return {**DEFAULT_SCARCITY_WEIGHTS, **overrides}
        return DEFAULT_SCARCITY_WEIGHTS


settings = Settings()
