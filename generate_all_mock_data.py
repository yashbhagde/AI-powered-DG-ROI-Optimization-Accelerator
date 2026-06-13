import subprocess
import sys
import os
import argparse


def run_script(script_name, num_assets=None):
    print(f"Running {script_name}...")
    cmd = [sys.executable, script_name]
    if num_assets is not None:
        cmd.extend(["--num-assets", str(num_assets)])
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}: {e.stderr}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Generate rich mock metadata for all catalog vendors.")
    parser.add_argument("--num-assets", type=int, default=None, help="Number of assets to generate per catalog vendor.")
    args = parser.parse_args()

    scripts = [
        os.path.join("alation", "mock_alation_generator.py"),
        os.path.join("collibra", "mock_collibra_generator.py"),
        os.path.join("purview", "mock_purview_generator.py"),
        os.path.join("ataccama", "mock_ataccama_generator.py"),
        os.path.join("informatica", "mock_informatica_generator.py"),
    ]

    print("=" * 80)
    print("Generating Rich Mock Metadata for All Catalog Vendors...")
    if args.num_assets:
        print(f"Target count: {args.num_assets} assets per vendor")
    print("=" * 80)

    for script in scripts:
        if os.path.exists(script):
            run_script(script, args.num_assets)
        else:
            print(f"Warning: Script '{script}' not found.", file=sys.stderr)

    print("\nAll mock catalog metadata files have been created successfully!")
    print("Check the workspace directory for the generated JSON files:")
    print(" - alation/sample_alation_metadata.json")
    print(" - collibra/sample_collibra_metadata.json")
    print(" - purview/sample_purview_metadata.json")
    print(" - ataccama/sample_ataccama_metadata.json")
    print(" - informatica/sample_informatica_metadata.json")
    print("=" * 80)


if __name__ == "__main__":
    main()
