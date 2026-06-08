from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./pulsermesh.db"
    api_key_secret: str = "changeme"
    node_id: str = ""
    node_domain: str = ""
    mesh_peer_urls: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
