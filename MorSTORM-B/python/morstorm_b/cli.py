import argparse
import json
from .pipeline import run
from .native.common import ParityDomainError


def main():
    parser = argparse.ArgumentParser(description="MorSTORM B: standalone Python drift correction and MorphoLibJ")
    parser.add_argument("config", help="Path to shared JSON configuration")
    parser.add_argument('--drift', choices=['meanshift','npcloud','rrnpcloud','aim','none','external_csv'], help='Select the native drift method')
    parser.add_argument('--output', help='Fresh output directory; relative paths resolve beside the configuration')
    args = parser.parse_args()
    try:
        result = run(args.config, method=args.drift, output_dir=args.output)
    except ParityDomainError as error:
        parser.exit(2, f'MorSTORM B: {error}\n')
    print(json.dumps({"status": result["status"], "localizations": result["localizations"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
