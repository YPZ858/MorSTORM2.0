import argparse
import json
from .pipeline import run


def main():
    parser = argparse.ArgumentParser(description="MorSTORM: SMLM to shared MorphoLibJ morphology")
    parser.add_argument("config", help="Path to shared JSON configuration")
    parser.add_argument('--drift', choices=['meanshift','npcloud','rrnpcloud','aim','none','external_csv'], help='Select the original author method')
    parser.add_argument('--output', help='Fresh output directory; relative paths resolve beside the configuration')
    args = parser.parse_args()
    result = run(args.config, method=args.drift, output_dir=args.output)
    print(json.dumps({"status": result["status"], "localizations": result["localizations"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
