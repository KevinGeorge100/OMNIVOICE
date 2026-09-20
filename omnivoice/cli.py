import argparse
import hashlib
import json
import secrets
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="OmniVoice development engine")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create a private .env without printing secrets")
    serve = sub.add_parser("serve", help="Start the local enterprise console and media engine")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    models = sub.add_parser("models", help="Download public Silero and optional embedding weights")
    models.add_argument("--semantic", action="store_true")
    args = parser.parse_args()
    if args.command == "init":
        path = Path(".env")
        if path.exists():
            print("Existing .env preserved.")
            return
        template = Path(".env.example").read_text(encoding="utf-8")
        with path.open("x", encoding="utf-8") as file:
            file.write(
                template.replace(
                    "OMNI_ADMIN_TOKEN=\n", "OMNI_ADMIN_TOKEN=" + secrets.token_urlsafe(48) + "\n"
                )
            )
        print("Created private .env with a generated administrator token. No credentials were printed.")
    elif args.command == "serve":
        import uvicorn

        # Carrier URLs can contain routing secrets. Never enable raw URL access logs.
        uvicorn.run(
            "omnivoice.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            workers=1,
            access_log=False,
            log_level="warning",
            ws_max_size=131072,
            timeout_graceful_shutdown=20,
        )
    else:
        from .config import Settings

        settings = Settings()
        path = settings.silero_model
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            # Versioned upstream source; retain its MIT license alongside the model.
            base = "https://raw.githubusercontent.com/snakers4/silero-vad/60b7ffa243625ebdc1070275a29f18c87843786a/"
            temporary = path.with_suffix(".download")
            urllib.request.urlretrieve(base + "src/silero_vad/data/silero_vad.onnx", temporary)
            from .vad import SileroFactory

            SileroFactory(temporary)
            temporary.replace(path)
            urllib.request.urlretrieve(base + "LICENSE", path.parent / "SILERO-LICENSE.txt")
        print("Silero ONNX installed and validated.")
        manifest = {"silero": {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
        if args.semantic:
            from fastembed import TextEmbedding

            model = TextEmbedding(
                model_name=settings.embedding_model, cache_dir=settings.embedding_cache, threads=1
            )
            list(model.embed(["OmniVoice model readiness check"]))
            manifest["embedding"] = {"model": settings.embedding_model, "cache": settings.embedding_cache}
            print("Embedding model installed. Set OMNI_SEMANTIC_ENABLED=true to enable it.")
        (path.parent / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
