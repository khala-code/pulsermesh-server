from pydantic_settings import BaseSettings
import uuid


class Settings(BaseSettings):
    api_key_secret: str = "changeme"
    database_url: str = "sqlite:///./pulsermesh.db"
    node_id: str = str(uuid.uuid4())  # stable per node in prod via .env

    class Config:
        env_file = ".env"


settings = Settings()
