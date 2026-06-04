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
        os.path.join("alation", "mock_alation_generator.py"),
        os.path.join("collibra", "mock_collibra_generator.py"),
        os.path.join("purview", "mock_purview_generator.py"),
        os.path.join("ataccama", "mock_ataccama_generator.py"),
        os.path.join("informatica", "mock_informatica_generator.py")
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
    print(" - alation/sample_alation_metadata.json")
    print(" - collibra/sample_collibra_metadata.json")
    print(" - purview/sample_purview_metadata.json")
    print(" - ataccama/sample_ataccama_metadata.json")
    print(" - informatica/sample_informatica_metadata.json")
    print("=" * 80)

if __name__ == "__main__":
    main()
