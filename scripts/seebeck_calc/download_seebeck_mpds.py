import polars as pl
from mpds_client import MPDSDataRetrieval, MPDSDataTypes

api_key = "HERE_YOUR_API_KEY"

def get_seebeck_with_temperature(formula: str, sg: int) -> pl.DataFrame:
    client = MPDSDataRetrieval(dtype=MPDSDataTypes.AB_INITIO, api_key=api_key)

    data = client.get_data(
        {"props": "Seebeck coefficient",
         "formulae": formula,
         "sgs": sg}
    )

    if not data:
        raise ValueError("No Seebeck data found")

    phase_id, formula, sg, entry, _, _, value = data[0]

    client2 = MPDSDataRetrieval(dtype=MPDSDataTypes.PEER_REVIEWED, api_key=api_key)
    full_data = client2.get_data(
        {"props": "atomic structure"},
        phases=[phase_id],
        fields={
            "S": [
                "phase_id",
                "chemical_formula",
                "occs_noneq",
                "cell_abc",
                "sg_n",
                "basis_noneq",
                "els_noneq",
                "entry",
                "condition",
            ]
        },
    )
            

    temperature = None

    for rec in full_data:
        if rec[-1]:
            if isinstance(rec[-1], list):
                for cond in rec[-1]:
                    if cond:
                        temperature = cond
                        break
            else:
                temperature = rec[-1]
            break

    records = [phase_id, formula, sg, entry, value, temperature]

    return records
    
results = []
for PHASE in [
    ("FeSe", "229"),
    ("SrO", "225"),
    ("ZnSc", "221"),
    ("NaBi", "123"),
    ("Os", "194"),
    ("LiCl", "225"),
    ("AlAs", "216"),
    ("Ni", "229"),
    ("ErSe", "225"),
    ("K2S", "225"),
    ("MgO", "225"),
]:
    formula, sg = PHASE
    print(f"Processing {formula} SG{sg}")
    try:
        res = get_seebeck_with_temperature(formula, int(sg))
        results.append(res)
    except Exception as e:
        print(f"  Error processing {formula} SG{sg}: {e}")
    
df = pl.DataFrame(results, schema=["phase_id", "formula", "sg", "entry", "seebeck", "temperature"])
df.write_csv("ab_initio_seebeck_data.csv")
