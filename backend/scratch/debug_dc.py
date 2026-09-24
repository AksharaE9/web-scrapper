import asyncio
import sys
sys.path.insert(0, 'c:/coding/web scrapper/leadcore-zero/backend')
from app.eval.relevance import evaluate_single_case
from pathlib import Path

async def main():
    result = await evaluate_single_case(Path('c:/coding/web scrapper/leadcore-zero/eval/relevance/degree_college_ameerpet.yaml'))
    print('Precision:', result['precision'])
    print('TP:', result['tp'], 'FP:', result['fp'], 'TN:', result['tn'], 'FN:', result['fn'])
    print('\nAll ACCEPTED decisions:')
    for d in result.get('all_decisions', []):
        if d['outcome'] == 'accepted':
            label = 'TRUE_POS' if d['ground_truth'] else 'FALSE_POS SEEDED=' + str(d.get('is_seeded_negative', False))
            print(f'  [{label}] {d["name"]} | stage={d["stage"]} | p={d["p"]}')
    print('\nFalse positives:')
    for fp in result.get('false_positives', []):
        print(f'  - {fp["name"]} | stage={fp["stage"]} | p={fp["p"]}')

asyncio.run(main())
