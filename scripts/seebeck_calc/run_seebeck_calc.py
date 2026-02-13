import os
import subprocess
from pathlib import Path

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

def create_input_file(dir_path):
    """Create INPUT file with predefined content in target directory"""
    input_path = dir_path / "INPUT"
    with open(input_path, "w") as f:
        f.write(INPUT_CONTENT)
    print(f"Created INPUT file")

def run_pproperties_in_directories(directories, engines_path, np=8):
    """
    Iterate through directories:
    1. Create standard INPUT file
    2. Run mpirun -np 8 Pproperties < INPUT > test.out
    3. Wait for completion before next directory
    """
    for dir_path in directories:
        dir_path = Path(dir_path)
        
        if not dir_path.is_dir():
            print(f"Warning: {dir_path} does not exist or is not a directory. Skipping.")
            continue
        
        print(f"Processing: {dir_path}")
        original_cwd = os.getcwd()
        
        try:
            # cd
            os.chdir(dir_path)
            
            #always create fresh INPUT file (overwrite existing)
            create_input_file(dir_path)
            
            # verify Pproperties executable exists
            engines_full_path = Path(engines_path)
            if not engines_full_path.exists():
                print(f"  Error: {engines_path} not found")
                continue
            
            #execute mpirun command
            print(f"  Running: mpirun -np {np} {engines_path} < INPUT > test.out")
            
            # cmd = ["mpirun", "-np", str(np), str(engines_full_path)]
            # add -v to see errors
            cmd = ["mpirun", "-np", str(np), "-v", str(engines_full_path)]
            
            with open("INPUT") as infile, open("test.out", "w") as outfile:
                result = subprocess.run(
                    cmd,
                    stdin=infile,
                    text=True,
                    cwd=dir_path
                )
            
            if result.returncode == 0:
                print("Successfully completed")
            else:
                print(f"Failed with return code {result.returncode}")
                
        except Exception as e:
            print(f"Error: {e}")
        finally:
            #always return to original dir
            try:
                os.chdir(original_cwd)
            except:
                pass
        
        print("---")

if __name__ == "__main__":
    import polars as pl

    df = pl.read_csv("/data/summary_2026_02_13_19_47_54.csv")
    filtered_df = df.filter(pl.col("H") == "PBE0")
    DIRECTORIES = [Path(p).parent for p in filtered_df['output_path']]
    
    ENGINES_PATH = "/root/projects/ab_initio_calculations/engines/Pproperties"
    
    run_pproperties_in_directories(DIRECTORIES, ENGINES_PATH)
