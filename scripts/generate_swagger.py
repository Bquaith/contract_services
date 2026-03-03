from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate OpenAPI/Swagger JSON from FastAPI app")
    parser.add_argument(
        "-o",
        "--output-file",
        default="swagger.json",
        help="Output path for generated OpenAPI JSON (default: swagger.json)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Write JSON without indentation",
    )
    return parser.parse_args()


def _bootstrap_pythonpath() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


def main() -> None:
    args = _parse_args()
    _bootstrap_pythonpath()

    try:
        from app.main import create_app

        app = create_app()
        swagger_dict = app.openapi()
        output_file_path = Path(args.output_file)
        output_file_path.parent.mkdir(parents=True, exist_ok=True)

        dumps_kwargs: dict[str, object] = {"ensure_ascii": False}
        if args.compact:
            dumps_kwargs["separators"] = (",", ":")
        else:
            dumps_kwargs["indent"] = 2

        output_file_path.write_text(
            json.dumps(swagger_dict, **dumps_kwargs),
            encoding="utf-8",
        )
        print(f"OpenAPI generated: {output_file_path}")

    except Exception as exc:
        print(f"Generate swagger file failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
