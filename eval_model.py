import sys

sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Payment, RecoveryCase
from src.features.root_cause_features import RootCauseFeatureExtractor
from src.models.root_cause_inference import RootCauseInferenceService

engine = create_engine("sqlite:///data/revive_dev.db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
session = SessionLocal()
service = RootCauseInferenceService()
extractor = RootCauseFeatureExtractor(session)

cases = (
    session.query(RecoveryCase, Payment)
    .join(Payment, RecoveryCase.source_id == Payment.payment_id)
    .all()
)

explicit_correct = 0
explicit_total = 0
ambiguous_correct = 0
ambiguous_total = 0

for case, payment in cases:
    true_label = payment.failure_reason
    if not true_label:
        continue

    features = extractor.extract_features(case)
    # inject the failure_code which is expected by the diagnostic engine to run the deterministic rules
    features["failure_code"] = payment.failure_code
    features["failure_reason"] = payment.failure_reason
    features["source_type"] = case.source_type

    pred_rc, conf, is_det = service.diagnose(features, case.customer_id)

    if payment.failure_code and payment.failure_code.startswith("ERR_GENERIC"):
        ambiguous_total += 1
        if pred_rc == true_label:
            ambiguous_correct += 1
    else:
        explicit_total += 1
        if pred_rc == true_label:
            explicit_correct += 1

print(
    f"Explicit Subset Accuracy: {explicit_correct}/{explicit_total} ({explicit_correct / max(1, explicit_total):.2f})"
)
print(
    f"Ambiguous Subset Accuracy: {ambiguous_correct}/{ambiguous_total} ({ambiguous_correct / max(1, ambiguous_total):.2f})"
)
print(
    f"Overall Accuracy: {(explicit_correct + ambiguous_correct) / (explicit_total + ambiguous_total):.2f}"
)
