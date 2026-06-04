import subprocess
import sys
import os

def run_script(script_name):
    print(f"Running {script_name}...")
    try:
        result = subprocess.run([sys.executable, script_name], check=True, capture_output=True, text=True)
        print(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}: {e.stderr}", file=sys.stderr)

def main():
    scripts = [
        "mock_alation_generator.py",
        "mock_collibra_generator.py",
        "mock_purview_generator.py",
        "mock_ataccama_generator.py",
        "mock_informatica_generator.py"
    ]
    
    print("=" * 80)
    print("Generating Rich Mock Metadata for All Catalog Vendors...")
    print("=" * 80)
    
    for script in scripts:
        if os.path.exists(script):
            run_script(script)
        else:
            print(f"Warning: Script '{script}' not found.", file=sys.stderr)
            
    print("\nAll mock catalog metadata files have been created successfully!")
    print("Check the workspace directory for the generated JSON files:")
    print(" - sample_alation_metadata.json")
    print(" - sample_collibra_metadata.json")
    print(" - sample_purview_metadata.json")
    print(" - sample_ataccama_metadata.json")
    print(" - sample_informatica_metadata.json")
    print("=" * 80)

if __name__ == "__main__":
    main()
