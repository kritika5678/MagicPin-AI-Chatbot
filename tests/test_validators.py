from models import CategoryContext, MerchantContext, TriggerContext, FullContext, MessageStrategy, ComposedMessage
from validators.message_validator import MessageValidator


def test_validator_rejects_unsupported_number():
    ctx = FullContext(
        category=CategoryContext(slug="dentists"),
        merchant=MerchantContext(merchant_id="m1", performance={"ctr": 0.02}),
        trigger=TriggerContext(id="t", scope="merchant", kind="perf_dip", source="internal", payload={}, urgency=1, suppression_key="x")
    )
    strategy = MessageStrategy(objective="ENGAGE", cta="open_ended", send_as="vera", language="english")
    msg = ComposedMessage(body="Your CTR is 9.99% right now. Want me to check?", cta="open_ended", send_as="vera", suppression_key="x", rationale="test")
    result = MessageValidator().validate(msg, ctx, strategy)
    assert not result.valid
    assert any("unsupported numeric claim" in e for e in result.errors)
