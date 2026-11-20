"""Independent file CLI using exactly the same API and Session as the service."""
import argparse
import json
import os

from algorithm import Session
from API import infer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--options", default="{}")
    parser.add_argument("--model-dir", default=os.getenv("MODEL_DIR", "/models"))
    parser.add_argument("--device", default=os.getenv("DEVICE", "cpu"))
    args = parser.parse_args()
    options = Session.validate_options(json.loads(args.options))
    session = Session(args.model_dir, args.device)
    try:
        metadata = infer(session, args.input, args.output, options)
        print(json.dumps(dict(success=True, algorithm_profile=session.profile, metadata=metadata)))
    finally:
        session.close()


if __name__ == "__main__":
    main()
