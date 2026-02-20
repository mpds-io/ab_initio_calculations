
import os
from yascheduler import Yascheduler
import os
from pathlib import Path
import base64


# INPUT file template content
INPUT_CONTENT = """NEWK
32 32
1 0
BOLTZTRA
TRANGE
300 600 300
MURANGE
-10 20 0.05
TDFRANGE
-10 20 0.05
RELAXTIM
10
END
END
"""


def create_input_file(dir_path: Path):
    """Create INPUT file with predefined content in target directory"""
    input_path = dir_path / "INPUT"
    with open(input_path, "w") as f:
        f.write(INPUT_CONTENT)
    print(f"Created INPUT file")
    return INPUT_CONTENT

def submit_yascheduler_task(input_file):
    """Give task to yascheduler"""
    target = os.path.abspath(input_file)
    work_folder = os.path.dirname(target)
    label = SETUP_INPUT.splitlines()[0]

    yac = Yascheduler()
    
    with open(target, encoding="utf-8") as f:
        SETUP_INPUT = f.read()

    with open(os.path.join(work_folder, "fort.9"), "rb") as f:
        fort9_b64 = base64.b64encode(f.read()).decode("ascii")
        

    result = yac.queue_submit_task(
        label,
        {
            "INPUT": SETUP_INPUT,
            "fort.9": fort9_b64,  
            "local_folder": work_folder,
        },
        "pproperties",
    )
    print(label)
    print(result)
    
    

def run_pproperties(directories: list):
    for dir_path in directories:
        dir_path = Path(dir_path)
        
        if not dir_path.is_dir():
            print(f"Warning: {dir_path} does not exist or is not a directory. Skipping.")
            continue
        
        print(f"Processing: {dir_path}")
        
        try:
            # cd
            os.chdir(dir_path)
            
            #always create fresh INPUT file (overwrite existing)
            create_input_file(dir_path)
            submit_yascheduler_task(dir_path / "INPUT")
            
        except Exception as e:
            print(f"Error during setup: {e}")
            continue
            
if __name__ == "__main__":
    import polars as pl

    # df = pl.read_csv("/data/summary_2026_02_13_19_47_54.csv")
    # filtered_df = df.filter(pl.col("H") == "PBE0")
    # DIRECTORIES = [Path(p).parent for p in filtered_df['output_path']]
    DIRECTORIES = [
        "/data/aiida/9f/84/eb21-3c02-4d4b-acb3-686bf2978e66", 
        "/data/aiida/03/b6/e269-1014-4636-9897-7f2c617b2cf9", 
        "/data/aiida/8b/a9/99fd-330d-4908-b587-92f7c6647c57", 
        "/data/aiida/2a/cb/c323-2ae7-4e12-8039-d807538e2024", 
        "/data/aiida/aa/9e/54ea-d183-4f3e-b138-6e620092310a", 
        "/data/aiida/3e/c5/8e6f-9ab3-4786-b044-bd49b755335e"
        
        # "/data/aiida/3e/c5/8e6f-9ab3-4786-b044-bd49b755335e"
    ]
    
    ENGINES_PATH = "/root/projects/ab_initio_calculations/engines/Pproperties"
    
    run_pproperties(DIRECTORIES)