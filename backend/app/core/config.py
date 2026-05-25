from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    deepseek_api_key: str = ""
    github_token: str = ""
    chroma_persist_dir: str = "./chroma_data"


settings = Settings()
