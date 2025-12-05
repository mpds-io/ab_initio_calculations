if __name__ == '__main__':
    from aiida.engine import submit
    from aiida.orm import Dict
    from mpds_aiida.workflows.fleur_mpds import MPDSFleurStructureWorkChain
    from aiida import load_profile
    from data.ref_structures import reference_states
    load_profile()    
    
    for row in reference_states:
        if row is None:
            continue
        try:    
            el = row.get('formula')
            sgs = row.get('sgs')
            
            if not el or not sgs:
                print(f"[WARNING] Skipping element with incomplete data: {row}")
                continue
            
            builder = MPDSFleurStructureWorkChain.get_builder()

            builder.mpds_query = Dict(dict={
                "formulae": el,
                "sgs": sgs
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
