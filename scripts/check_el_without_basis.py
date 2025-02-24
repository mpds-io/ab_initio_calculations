import periodictable
import yaml
import os


if __name__ == "__main__":
    CONF = "./conf/conf.yaml"

    with open(CONF, 'r') as file:
        dir = yaml.safe_load(file)['basis_sets_path']

    files = [f.replace(".basis", "") for f in os.listdir(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            dir
        )
    )]
        
    els_no_basis = []
    for element in periodictable.elements:
        if element.symbol not in files:
            els_no_basis.append(element)
            
    print(els_no_basis)