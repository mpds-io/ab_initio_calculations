import os

def find_fort_and_input(root_dir: str) -> dict:
    """
    Find fort.87 and INPUT files in root_dir and return a dict with error description as key
    and list of chemical formulas as value.
    """
    error_dict = {}  
    # for file in main dir
    for root, dirs, files in os.walk(root_dir):
        if 'fort.87' in files:
            with open(os.path.join(root, 'fort.87'), 'r') as fort_file:
                fort_content = fort_file.read().strip()
            
            if 'INPUT' in files:
                # just first row
                with open(os.path.join(root, 'INPUT'), 'r') as input_file:
                    first_line = input_file.readline().strip()
                
                if fort_content not in error_dict:
                    error_dict[fort_content] = []
                error_dict[fort_content].append(first_line)
    
    return error_dict

if __name__ == '__main__':
    root_dir = './output/'
    error_dict = find_fort_and_input(root_dir)

    for error, structures in error_dict.items():
        print(f"Error: {error}")
        print("Structure (chemical formula):")
        for structure in structures:
            print(f"  - {structure}")

