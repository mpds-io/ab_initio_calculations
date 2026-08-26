# Phonon calculation analysis via AiiDA

## Summary

- Total phonon-related nodes: **250**
- Unique materials: **54**
- Materials with at least one successful calcjob (Finished [0]): **3**
- Materials with no successful calcjobs: **51**

### Calcjobs (CrystalParallelCalculation)
- parser_error: 51
- ok: 36
- crystal_symmops: 21
- invalid_output: 4
- killed: 3
- missing_output: 2

### Workchains (BaseCrystalWorkChain)
- ok: 93
- workchain_bug: 19
- killed: 13

### PhonopyFleurWorkChain
- phonopy_fleur: 8

## Error classes

- **ok**: Finished [0], no errors
- **parser_error**: Excepted: aiida-crystal-dft parser bug (Symbol lists / unhashable type). CRYSTAL finished normally, but the parser crashed.
- **crystal_symmops**: Finished [400]: CRYSTAL failed with 'ERROR **** MULTIP **** SYMMOPS DO NOT FORM A GROUP'.
- **workchain_bug**: Excepted: BaseCrystalWorkChain bug (AttributeError: 'ExitCodesNamespace' has no attribute 'UNKNOWN_ERROR').
- **killed**: Process killed manually (Killed).
- **phonopy_fleur**: Excepted: PhonopyFleurWorkChain — FileNotFoundError: FLEUR_INPGEN_PATH is not set.
- **invalid_output**: Excepted: the parser could not read the CRYSTAL output (FileNotFoundError: ... is not a valid CRYSTAL output file).
- **missing_output**: Excepted: OUTPUT file missing from retrieved (FileNotFoundError: object with path `OUTPUT` does not exist).

## Fully successful materials

| Material | Calcjobs OK | PKs |
|---|---|---|
| CRYSTAL optimization step | 32 | 58756, 62126, 59306, 59405, 59249, 59428, 61972, 61109, 61452, 61531, 61474, 61490, 62454, 61839, 61548, 63633, 63649, 63671, 63856, 63979, 63974, 64179, 64221, 64257, 67198, 67214, 67236, 67723, 67739, 68462, 86219, 86296 |
| MgO/225 | 3 | 55142, 55039, 55775 |
| MgO_test | 1 | 55942 |

## Materials with no successful calcjobs

### parser_error (32 materials)

Excepted: aiida-crystal-dft parser bug (Symbol lists / unhashable type). CRYSTAL finished normally, but the parser crashed.

- ArS375021 — calcjobs: 2, errors: parser_error
- Ar_S375021 — calcjobs: 1, errors: parser_error
- As_S382875 — calcjobs: 1, errors: parser_error
- BS1234812 — calcjobs: 2, errors: parser_error
- B_S1620211 — calcjobs: 1, errors: parser_error
- BiS1959032 — calcjobs: 2, errors: parser_error
- Ca_pbe_S530909 — calcjobs: 1, errors: parser_error
- Ca_x_S530909 — calcjobs: 1, errors: parser_error
- HfS1012752 — calcjobs: 2, errors: parser_error
- LaS535140 — calcjobs: 2, errors: parser_error
- MgS312553 — calcjobs: 2, errors: parser_error
- NS1251868 — calcjobs: 2, errors: parser_error
- NiS452609 — calcjobs: 2, errors: invalid_output, parser_error
- Ni_S380367 — calcjobs: 1, errors: parser_error
- NpS527233 — calcjobs: 2, errors: invalid_output, parser_error
- PrS1625315 — calcjobs: 2, errors: invalid_output, parser_error
- RbS1715170 — calcjobs: 2, errors: parser_error
- Rb_S526885 — calcjobs: 1, errors: parser_error
- S_S1931383 — calcjobs: 1, errors: parser_error
- Sb_S458370 — calcjobs: 1, errors: parser_error
- Se_S381985 — calcjobs: 1, errors: parser_error
- Sn_S533526 — calcjobs: 1, errors: parser_error
- SrS456028 — calcjobs: 2, errors: parser_error
- Sr_S250522 — calcjobs: 1, errors: parser_error
- TbS1254043 — calcjobs: 2, errors: parser_error
- TcS533193 — calcjobs: 1, errors: parser_error
- Te_S453334 — calcjobs: 1, errors: parser_error
- TlS1500024 — calcjobs: 2, errors: invalid_output, parser_error
- VS535016 — calcjobs: 2, errors: parser_error
- V_S535016 — calcjobs: 1, errors: parser_error
- WS250696 — calcjobs: 2, errors: parser_error
- W_S250696 — calcjobs: 1, errors: parser_error

### crystal_symmops (11 materials)

Finished [400]: CRYSTAL failed with 'ERROR **** MULTIP **** SYMMOPS DO NOT FORM A GROUP'.

- CS546295 — calcjobs: 2, errors: crystal_symmops
- C_S546299 — calcjobs: 1, errors: crystal_symmops
- Co_S311946 — calcjobs: 1, errors: crystal_symmops
- GeS1721789 — calcjobs: 2, errors: crystal_symmops
- Ge_S1721789 — calcjobs: 1, errors: crystal_symmops
- Hf_S553651 — calcjobs: 1, errors: crystal_symmops
- SiS304951 — calcjobs: 2, errors: crystal_symmops
- Si_S553634 — calcjobs: 1, errors: crystal_symmops
- TeS375096 — calcjobs: 2, errors: crystal_symmops
- Ti_S1503169 — calcjobs: 1, errors: crystal_symmops
- Y_S1542266 — calcjobs: 1, errors: crystal_symmops

### other_error (8 materials)

Other error (unclassified).

- Au2U/191 - phonons — calcjobs: 0, errors: 
- B2O3/152 - phonons — calcjobs: 0, errors: 
- BaSn3/194 - phonons — calcjobs: 0, errors: 
- BiSe/164 - phonons — calcjobs: 0, errors: 
- Ce5Ge3/193 - phonons — calcjobs: 0, errors: 
- Co2As/189 - phonons — calcjobs: 0, errors: 
- CrSb/194 - phonons — calcjobs: 0, errors: 
- DyNi5/191 - phonons — calcjobs: 0, errors: 

## Detailed node list

| PK | Label | Type | State | Exit | Error class |
|---|---|---|---|---|---|
| 1733 | BiS1959032: Phonon frequencies | workchain | killed | - | killed |
| 1743 | RbS1715170: Phonon frequencies | workchain | killed | - | killed |
| 1794 | WS250696: Phonon frequencies | workchain | killed | - | killed |
| 1822 | HfS1012752: Phonon frequencies | workchain | killed | - | killed |
| 1847 | SrS456028: Phonon frequencies | workchain | killed | - | killed |
| 1897 | MgS312553: Phonon frequencies | workchain | killed | - | killed |
| 1912 | BS1234812: Phonon frequencies | workchain | killed | - | killed |
| 1932 | ArS375021: Phonon frequencies | workchain | killed | - | killed |
| 1942 | GeS1721789: Phonon frequencies | workchain | killed | - | killed |
| 1957 | TlS1500024: Phonon frequencies | workchain | killed | - | killed |
| 3422 | BiS1959032: Phonon frequencies | workchain | finished | 0 | ok |
| 3444 | RbS1715170: Phonon frequencies | workchain | finished | 0 | ok |
| 3530 | WS250696: Phonon frequencies | workchain | finished | 0 | ok |
| 3579 | HfS1012752: Phonon frequencies | workchain | finished | 0 | ok |
| 3603 | SrS456028: Phonon frequencies | workchain | finished | 0 | ok |
| 3615 | BiS1959032: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 3645 | RbS1715170: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 3662 | BS1234812: Phonon frequencies | workchain | finished | 0 | ok |
| 3689 | MgS312553: Phonon frequencies | workchain | finished | 0 | ok |
| 3707 | WS250696: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 3717 | ArS375021: Phonon frequencies | workchain | finished | 0 | ok |
| 3729 | GeS1721789: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 3737 | HfS1012752: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 3749 | TlS1500024: Phonon frequencies | workchain | finished | 0 | ok |
| 3761 | SrS456028: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 3799 | BS1234812: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 3817 | MgS312553: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 3832 | LaS535140: Phonon frequencies | workchain | finished | 0 | ok |
| 3849 | ArS375021: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 3854 | GeS1721789: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 3859 | SiS304951: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 3875 | TlS1500024: Phonon frequencies [1] | calcjob | excepted | - | invalid_output |
| 3886 | TeS375096: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 3937 | VS535016: Phonon frequencies | workchain | finished | 0 | ok |
| 3961 | LaS535140: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 3975 | SiS304951: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 3980 | NS1251868: Phonon frequencies | workchain | finished | 0 | ok |
| 3988 | TeS375096: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 4017 | VS535016: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 4030 | TbS1254043: Phonon frequencies | workchain | finished | 0 | ok |
| 4037 | NS1251868: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 4050 | CS546295: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 4063 | TbS1254043: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 4071 | CS546295: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 4092 | NpS527233: Phonon frequencies | workchain | finished | 0 | ok |
| 4097 | NpS527233: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 4116 | NiS452609: Phonon frequencies | workchain | finished | 0 | ok |
| 4121 | NiS452609: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 4132 | PrS1625315: Phonon frequencies | workchain | finished | 0 | ok |
| 4137 | PrS1625315: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 5316 | TcS533193: Phonon frequencies | workchain | finished | 0 | ok |
| 5411 | BiS1959032: Phonon frequencies | workchain | finished | 0 | ok |
| 5431 | RbS1715170: Phonon frequencies | workchain | finished | 0 | ok |
| 5483 | WS250696: Phonon frequencies | workchain | finished | 0 | ok |
| 5594 | HfS1012752: Phonon frequencies | workchain | finished | 0 | ok |
| 5624 | SrS456028: Phonon frequencies | workchain | finished | 0 | ok |
| 5636 | BS1234812: Phonon frequencies | workchain | finished | 0 | ok |
| 5648 | TcS533193: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 5694 | MgS312553: Phonon frequencies | workchain | finished | 0 | ok |
| 5731 | ArS375021: Phonon frequencies | workchain | finished | 0 | ok |
| 5742 | BiS1959032: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 5747 | GeS1721789: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 5754 | RbS1715170: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 5766 | TlS1500024: Phonon frequencies | workchain | finished | 0 | ok |
| 5800 | WS250696: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 5822 | LaS535140: Phonon frequencies | workchain | finished | 0 | ok |
| 5858 | SiS304951: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 5882 | TeS375096: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 5908 | HfS1012752: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 5916 | SrS456028: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 5921 | BS1234812: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 5945 | MgS312553: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 5960 | ArS375021: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 5965 | GeS1721789: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 5975 | TlS1500024: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 5993 | LaS535140: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 6009 | VS535016: Phonon frequencies | workchain | finished | 0 | ok |
| 6018 | SiS304951: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 6026 | TeS375096: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 6055 | CS546295: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 6067 | NS1251868: Phonon frequencies | workchain | finished | 0 | ok |
| 6078 | VS535016: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 6094 | CS546295: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 6104 | NS1251868: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 6117 | TbS1254043: Phonon frequencies | workchain | finished | 0 | ok |
| 6125 | TbS1254043: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 6151 | NpS527233: Phonon frequencies | workchain | finished | 0 | ok |
| 6156 | NpS527233: Phonon frequencies [1] | calcjob | excepted | - | invalid_output |
| 6178 | NiS452609: Phonon frequencies | workchain | finished | 0 | ok |
| 6183 | NiS452609: Phonon frequencies [1] | calcjob | excepted | - | invalid_output |
| 6197 | PrS1625315: Phonon frequencies | workchain | finished | 0 | ok |
| 6202 | PrS1625315: Phonon frequencies [1] | calcjob | excepted | - | invalid_output |
| 40584 | Si_S553634: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 40589 | Si_S553634: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 40614 | Ar_S375021: Phonon frequencies | workchain | finished | 0 | ok |
| 40619 | Ar_S375021: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 40654 | V_S535016: Phonon frequencies | workchain | finished | 0 | ok |
| 40659 | V_S535016: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 40676 | S_S1931383: Phonon frequencies | workchain | finished | 0 | ok |
| 40681 | S_S1931383: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 40692 | Ti_S1503169: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 40697 | Ti_S1503169: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 40714 | Co_S311946: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 40719 | Co_S311946: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 40730 | Ni_S380367: Phonon frequencies | workchain | finished | 0 | ok |
| 40735 | Ni_S380367: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 40758 | Ge_S1721789: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 40763 | Ge_S1721789: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 40774 | As_S382875: Phonon frequencies | workchain | finished | 0 | ok |
| 40779 | As_S382875: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 40790 | Se_S381985: Phonon frequencies | workchain | finished | 0 | ok |
| 40795 | Se_S381985: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 40806 | Sr_S250522: Phonon frequencies | workchain | finished | 0 | ok |
| 40811 | Sr_S250522: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 40822 | Rb_S526885: Phonon frequencies | workchain | finished | 0 | ok |
| 40827 | Rb_S526885: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 40844 | B_S1620211: Phonon frequencies | workchain | finished | 0 | ok |
| 40849 | B_S1620211: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 40860 | Y_S1542266: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 40865 | Y_S1542266: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 40927 | Sn_S533526: Phonon frequencies | workchain | finished | 0 | ok |
| 40932 | Sn_S533526: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 40943 | Sb_S458370: Phonon frequencies | workchain | finished | 0 | ok |
| 40948 | Sb_S458370: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 40959 | Te_S453334: Phonon frequencies | workchain | finished | 0 | ok |
| 40964 | Te_S453334: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 41067 | Hf_S553651: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 41072 | Hf_S553651: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 41095 | W_S250696: Phonon frequencies | workchain | finished | 0 | ok |
| 41100 | W_S250696: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 41197 | C_S546299: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 41202 | C_S546299: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 42038 | Ca_x_S530909: Phonon frequencies | workchain | finished | 0 | ok |
| 42043 | Ca_x_S530909: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 42062 | Ca_pbe_S530909: Phonon frequencies | workchain | finished | 0 | ok |
| 42067 | Ca_pbe_S530909: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 45447 | MgO/225: Phonon frequencies | workchain | killed | - | killed |
| 45452 | MgO/225: Phonon frequencies [1] | calcjob | killed | - | killed |
| 55034 | MgO/225: Phonon frequencies | workchain | finished | 0 | ok |
| 55039 | MgO/225: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 55137 | MgO/225: Phonon frequencies | workchain | finished | 0 | ok |
| 55142 | MgO/225: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 55770 | MgO/225: Phonon frequencies | workchain | finished | 0 | ok |
| 55775 | MgO/225: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 55937 | MgO_test: Phonon frequencies | workchain | finished | 0 | ok |
| 55942 | MgO_test: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 58750 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 58756 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 59244 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 59249 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 59301 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 59306 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 59400 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 59405 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 59423 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 59428 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 61104 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 61109 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 61447 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 61452 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 61469 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 61474 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 61485 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 61490 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 61504 | CRYSTAL optimization step: Phonon frequencies | workchain | killed | - | killed |
| 61509 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | killed | - | killed |
| 61526 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 61531 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 61543 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 61548 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 61797 | CRYSTAL optimization step: Phonon frequencies | workchain | killed | - | killed |
| 61802 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | killed | - | killed |
| 61834 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 61839 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 61967 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 61972 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 62121 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 62126 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 62449 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 62454 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 63628 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 63633 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 63644 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 63649 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 63666 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 63671 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 63851 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 63856 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 63964 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 63969 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 63974 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 63979 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 64174 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 64179 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 64190 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 64196 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 64216 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 64221 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 64252 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 64257 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 67171 | CRYSTAL optimization step: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 67176 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 67193 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 67198 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 67209 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 67214 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 67231 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 67236 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 67267 | CRYSTAL optimization step: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 67272 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 67302 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 67307 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 67330 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 67335 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 67346 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 67351 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | excepted | - | missing_output |
| 67718 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 67723 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 67734 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 67739 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 67863 | CRYSTAL optimization step: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 67868 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 67879 | CRYSTAL optimization step: Phonon frequencies [2] - restart | calcjob | finished | 400 | crystal_symmops |
| 67916 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 67921 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 67940 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 67945 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 68037 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 68042 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 68071 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 68076 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | excepted | - | missing_output |
| 68251 | CRYSTAL optimization step: Phonon frequencies | workchain | excepted | - | workchain_bug |
| 68256 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 400 | crystal_symmops |
| 68263 | CRYSTAL optimization step: Phonon frequencies [2] - restart | calcjob | finished | 400 | crystal_symmops |
| 68276 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 68281 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | excepted | - | parser_error |
| 68457 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 68462 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 69694 | BiSe/164 - phonons | phonopyfleur | excepted | - | phonopy_fleur |
| 69799 | B2O3/152 - phonons | phonopyfleur | excepted | - | phonopy_fleur |
| 69965 | DyNi5/191 - phonons | phonopyfleur | excepted | - | phonopy_fleur |
| 69972 | CrSb/194 - phonons | phonopyfleur | excepted | - | phonopy_fleur |
| 70996 | Ce5Ge3/193 - phonons | phonopyfleur | excepted | - | phonopy_fleur |
| 71002 | Co2As/189 - phonons | phonopyfleur | excepted | - | phonopy_fleur |
| 71012 | BaSn3/194 - phonons | phonopyfleur | excepted | - | phonopy_fleur |
| 72237 | Au2U/191 - phonons | phonopyfleur | excepted | - | phonopy_fleur |
| 86214 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 86219 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
| 86291 | CRYSTAL optimization step: Phonon frequencies | workchain | finished | 0 | ok |
| 86296 | CRYSTAL optimization step: Phonon frequencies [1] | calcjob | finished | 0 | ok |
