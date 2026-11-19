# Vazhdimi i ISS — checkpoint i ri

Rezultati i verifikuar: **142/148 kube**, **535 komanda**, fitness **-0.9407436801881247**.

Pikënisja: 140/148, 530 komanda, fitness -0.9249794238683127. Përmirësimi i fitness-it: 0.0157642563198120.

Pa komanda joefektive. Çdo prefiks u kontrollua nga simulatori zyrtar në proces të veçantë.

## Eksperimentet e kryera

| Metoda | Statusi | Kube | Komanda | Fitness | Sekonda |
|---|---|---:|---:|---:|---:|
| vacancy_continuation | completed | 140 | 530 | -0.9249794238683127 | 70.934 |
| prepared_command_pruning | completed | 140 | 522 | -0.9251534391534392 | 165.659 |
| safe_command_deletion | completed | 140 | 522 | -0.9251534391534392 | 178.469 |
| temporary_displacement | completed | 141 | 529 | -0.9329376837154617 | 68.493 |
| multi_cube_best_first | completed_finite_trials | 142 | 537 | -0.9407001763668429 | 282.505 |
| vacancy_continuation | completed | 142 | 537 | -0.9407001763668429 | 0.109 |
| prepared_command_pruning | completed | 142 | 535 | -0.9407436801881247 | 52.672 |
| safe_command_deletion | completed | 142 | 535 | -0.9407436801881247 | 183.575 |
| saved_frontier_integrity | completed_checks | 142 | 535 | -0.9407436801881247 | 3.158 |
| independent_final_verification | completed | 142 | 535 | -0.9407436801881247 | 23.378 |

Kohët më sipër janë kohët e fazave që përfunduan; koha e përgatitjes, rindërtimi i parë, procesi i ndërprerë për përshpejtim dhe kompilimi regjistrohen veçmas në logs/events.jsonl dhe logs/console_continue.py.log. Nuk numërohen si prova të përfunduara.

## Çfarë mbetet

- Continue the saved multi-cube heaps via code/launch.py extend.py, using each heap's stored verified prefix and comparing candidates with the GLOBAL latest best. Do not rebuild the heap. Historical starting solutions remain valid search branches.
- Investigate additional support relocations beyond newly unlocked support cubes.
- Explore larger groups or deeper paths; the search is not an exhaustive proof.

ISS nuk shpallet i përfunduar. Provat me kuotë/depth të kufizuar nuk provojnë që nuk ekziston një zgjidhje më e mirë.

Zgjidhja: `outputs/best_0008.npy`; kopje e lehtë për Kaggle: `outputs/zgjidhja_me_e_mire.npy`.

Vazhdimi: lexo RESUME_STATE.json dhe KAGGLE_CELLS.md. Notebook-u origjinal dhe checkpoint-et e mëparshme janë ruajtur të paprekura.
