from __future__ import annotations
from datetime import datetime, timezone
from detection.auto_reply_detector import AutoReplyDetector
from detection.intent_detector import IntentDetector
from models.conversation import ConversationState, ConversationTurn


OUT_OF_SCOPE_HINTS = ("gst", "tax filing", "ca", "itr", "accounting")


class ConversationHandler:
    def __init__(self):
        self.auto_reply = AutoReplyDetector()
        self.intent = IntentDetector()

    def respond(self, state: ConversationState, merchant_message: str) -> dict:
        prior = [t.message for t in state.turns if t.role == "merchant"]
        auto = self.auto_reply.detect(merchant_message, prior)
        intent = self.intent.classify(merchant_message)

        state.turns.append(ConversationTurn(role="merchant", message=merchant_message, intent=intent.intent))
        state.last_intent = intent.intent
        state.last_inbound_at = datetime.now(timezone.utc)

        if intent.intent in {"stop", "not_interested", "negative_interest"}:
            state.status = "NOT_INTERESTED"
            body = "Samajh gaya. Main yahin stop karti hoon — best wishes!"
            state.turns.append(ConversationTurn(role="vera", message=body))
            return {"action": "end", "mode": "EXIT", "body": body, "cta": "none", "rationale": "Merchant explicitly opted out or declined further messaging.", "state": state.model_dump(mode="json")}

        if auto.is_auto_reply:
            state.status = "AUTO_REPLY_DETECTED"
            state.retry_count += 1
            if state.retry_count >= 3:
                state.status = "EXITED"
                return {"action": "end", "mode": "EXIT", "rationale": "Auto-reply repeated 3 times with no real engagement; closing conversation."}
            wait = 86400 if state.retry_count >= 2 else 14400
            return {"action": "wait", "mode": "WAIT", "wait_seconds": wait, "rationale": f"Detected likely WhatsApp auto-reply; backing off before retry {state.retry_count + 1}."}

        if intent.intent in {"join", "start_action", "update_profile", "create_offer", "approve", "positive_interest"}:
            state.status = "ACTION_PENDING"
            state.current_goal = intent.intent
            body = "Great — let's move to the action step. I’ll take the next concrete step from here."
            cta = "binary_yes_no"
            state.turns.append(ConversationTurn(role="vera", message=body))
            return {"action": "send", "mode": "ACTION", "body": body, "cta": cta, "rationale": "Explicit positive/action intent detected; switched directly from qualification to execution.", "state": state.model_dump(mode="json")}

        if any(x in merchant_message.lower() for x in OUT_OF_SCOPE_HINTS):
            state.status = "ENGAGED"
            body = "I’ll leave that to your CA — it’s outside what I can help with directly. Coming back to the current Vera task: want me to continue with the original next step?"
            state.turns.append(ConversationTurn(role="vera", message=body))
            return {"action": "send", "mode": "ENGAGE", "body": body, "cta": "open_ended", "rationale": "Out-of-scope request politely declined and conversation redirected to the active goal."}

        state.status = "ENGAGED"
        body = "Got it. Tell me the exact thing you want to do next, and I’ll keep it to one concrete step."
        state.turns.append(ConversationTurn(role="vera", message=body))
        return {"action": "send", "mode": "ENGAGE", "body": body, "cta": "open_ended", "rationale": "General engaged response; asks for the next concrete action."}


def respond(state: ConversationState, merchant_message: str) -> dict:
    return ConversationHandler().respond(state, merchant_message)
