from pathlib import Path
import json
from loaders.context_loader import ContextRepository
from bot import compose

root = Path(__file__).resolve().parent
repo = ContextRepository(root / "dataset")
pairs = json.loads((root / "dataset" / "test_pairs.json").read_text())['pairs']

for pair in pairs:
    merchant = repo.merchant(pair['merchant_id'])
    category = repo.category(merchant.category_slug)
    trigger = repo.trigger(pair['trigger_id'])
    customer = repo.customer(pair['customer_id']) if pair.get('customer_id') else None
    out = compose(category.model_dump(mode='json'), merchant.model_dump(mode='json'), trigger.model_dump(mode='json'), customer.model_dump(mode='json') if customer else None)
    print(pair['test_id'], pair['trigger_id'], '=>', out['send_as'], '|', out['cta'], '|', out['body'])
