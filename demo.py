from pathlib import Path
from loaders.context_loader import ContextRepository
from bot import compose

ROOT = Path(__file__).parent / "demo_dataset"
repo = ContextRepository(ROOT)

category = repo.category("dentists").model_dump()
merchant = repo.merchant("drmeera").model_dump()
trigger = repo.trigger("research_digest").model_dump(mode="json")
print("MERCHANT EXAMPLE")
print(compose(category, merchant, trigger))

customer = repo.customer("priya").model_dump()
trigger_customer = repo.trigger("recall_due").model_dump(mode="json")
print("\nCUSTOMER EXAMPLE")
print(compose(category, merchant, trigger_customer, customer))
