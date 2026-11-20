"""JSON adapter for the pure support core; never overwrites an existing report."""
import argparse
import json
from pathlib import Path
from support_core import mass_properties, assess_support


def check(source, output):
    source, output = Path(source).expanduser().resolve(), Path(output).expanduser().resolve()
    package = Path(__file__).resolve().parent.parent
    if output == source or output.is_relative_to(package):
        raise ValueError("Use a separate report outside the package")
    if output.exists():
        raise FileExistsError(output)
    data = json.loads(source.read_text())
    parts = [mass_properties(**part) if 'vertices' in part else part for part in data['parts']]
    result = assess_support(parts, data['contacts_mm'], gravity=data['gravity'])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = check(args.input, args.output)
    print(json.dumps(result, indent=2))
    return 0 if result['center_inside_support_polygon'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
