"""OpenEnv-compatible server entry point."""

from app.main import app  # noqa: F401


def main(host: str = "0.0.0.0", port: int = 7860) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
