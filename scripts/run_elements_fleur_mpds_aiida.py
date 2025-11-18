if __name__ == '__main__':
    from aiida.engine import submit
    from aiida.orm import Dict
    from mpds_aiida.workflows.fleur_mpds import MPDSFleurStructureWorkChain
    from aiida import load_profile
    from ab_initio_calculations.utils.chemical_utils import (
        get_list_of_basis_elements,
    )
    load_profile()
    
    for el in get_list_of_basis_elements():
        try:    
            builder = MPDSFleurStructureWorkChain.get_builder()

            builder.mpds_query = Dict(dict={
                "formulae": el,
                "sgs": 221,
                "classes": "unary",
            })
        

            builder.workchain_options = Dict(dict={
                'options': {
                    'optimize_structure': True,
                    'need_phonons': False,
                    'optimizer': 'Adam',
                    "calculator": "scf"
                }
            })

            wc = submit(builder)
            print(f'Launched Fleur MPDS Structure WorkChain with PK={wc.pk}')
        except Exception as e:
            print(f"Error processing element {el}: {e}")
