from pydantic_settings import BaseSettings
from pydantic import ConfigDict
import uuid


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    api_key_secret: str = "changeme"
    database_url: str = "sqlite:///./pulsermesh.db"
    node_id: str = str(uuid.uuid4())


settings = Settings()
