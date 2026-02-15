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


def create_input_file(dir_path: Path):
    """Create INPUT file with predefined content in target directory"""
    input_path = dir_path / "INPUT"
    with open(input_path, "w") as f:
        f.write(INPUT_CONTENT)
    print(f"Created INPUT file")


def cleanup_pe_files(dir_path: Path):
    """Delete all *.pe* files from directory (fort.3.pe0, fort.10.pe7 etc.)"""
    dir_path = Path(dir_path)
    deleted_count = 0
    
    for pe_file in dir_path.glob("**/*.pe*"):
        try:
            pe_file.unlink()
            deleted_count += 1
        except Exception as e:
            print(f"Failed to delete {pe_file}: {e}")
    
    if deleted_count > 0:
        print(f"Deleted {deleted_count} *.pe* files")


def run_pproperties_in_directories(directories: list, engines_path: Path, np: int = 8):
    """
    Iterate through directories:
    1. Create standard INPUT file
    2. Run mpirun -np 8 Pproperties < INPUT > test.out
    3. Wait for completion before next directory
    4. Cleanup *.pe* files after each run
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
            print(f"Running: mpirun -np {np} {engines_path} < INPUT > test.out")
            
            # add -v to see errors
            cmd = ["mpirun", "-np", str(np), "-v", str(engines_full_path)]

            print(f"Running: {' '.join(cmd)} < INPUT > test.out")

            with open(os.path.join(dir_path, "INPUT"), "r") as infile, \
                open(os.path.join(dir_path, "test.out"), "w") as outfile:
                
                result = subprocess.run(
                    cmd, 
                    stdin=infile,   
                    stdout=outfile,  
                    stderr=subprocess.STDOUT, 
                    cwd=dir_path
                )
                            
            if result.returncode == 0:
                print("Successfully completed")
            else:
                print(f"Failed with return code {result.returncode}")
            cleanup_pe_files(dir_path)
                
        except Exception as e:
            print(f"Error: {e}")
            cleanup_pe_files(dir_path)
        
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
