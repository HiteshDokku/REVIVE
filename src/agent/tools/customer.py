"""Tools for accessing customer data."""

import uuid
from typing import Any

from src.database.models import Interaction, Intervention


def get_customer_history(
    customer_id: uuid.UUID,
    past_interventions: list[Intervention],
    past_interactions: list[Interaction],
) -> dict[str, Any]:
    """
    Retrieve historical context for a customer.
    In a real system, this would query the DB. Since our tools are
    state-reducer oriented, we format the provided state history.
    """
    return {
        "customer_id": str(customer_id),
        "total_interventions": len(past_interventions),
        "total_interactions": len(past_interactions),
        "promises_to_pay": sum(1 for i in past_interactions if i.promise_to_pay),
    }
