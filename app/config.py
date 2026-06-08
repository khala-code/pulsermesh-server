from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Dict
import uuid


# Default scarcity weights for known domains.
# Override per-node via SCARCITY_WEIGHTS env var (JSON) or node_config.yaml.
# These are the T_scarcity diagonal entries — the innermost transform.
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

    # JSON string override: '{"water": 2.0, "default": 1.0}'
    scarcity_weights_json: str = ""

    def scarcity_weights(self) -> Dict[str, float]:
        if self.scarcity_weights_json:
            import json
            overrides = json.loads(self.scarcity_weights_json)
            return {**DEFAULT_SCARCITY_WEIGHTS, **overrides}
        return DEFAULT_SCARCITY_WEIGHTS


settings = Settings()
