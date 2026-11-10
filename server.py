"""Task 1: strict MCP tools served over STDIO."""
import logging
import re
import sys
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

# FastMCP's protocol output is stdout. Keep all application diagnostics on stderr.
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("quillrai.mcp")

mcp = FastMCP("quillrai-customer-tools")

CUSTOMERS = {
    "CUST-00001": {"customer_id": "CUST-00001", "name": "Asha Patel", "status": "active"},
    "CUST-00002": {"customer_id": "CUST-00002", "name": "Rahul Shah", "status": "active"},
}
refund_events = []


def validate_customer_id(customer_id: str) -> str:
    if not re.fullmatch(r"CUST-[0-9]{5}", customer_id):
        raise ValueError("customer_id must match CUST-XXXXX (five digits)")
    return customer_id


@mcp.tool()
def get_customer_record(
    customer_id: Annotated[str, Field(pattern=r"^CUST-[0-9]{5}$", description="Customer ID, e.g. CUST-00001")]
) -> dict:
    """Return a mock customer record for a valid customer ID."""
    validate_customer_id(customer_id)
    record = CUSTOMERS.get(customer_id)
    if record is None:
        return {"found": False, "customer_id": customer_id}
    return {"found": True, "customer": record}


@mcp.tool()
def trigger_refund(
    customer_id: Annotated[str, Field(pattern=r"^CUST-[0-9]{5}$")],
    amount: Annotated[float, Field(gt=0, allow_inf_nan=False, description="Positive refund amount")],
    reason: Annotated[str, Field(min_length=10, max_length=500)],
) -> dict:
    """Create a simulated refund request; no real payment is processed."""
    validate_customer_id(customer_id)
    if customer_id not in CUSTOMERS:
        raise ValueError("Unknown customer_id")
    event = {
        "refund_id": f"REF-{len(refund_events) + 1:05d}",
        "customer_id": customer_id,
        "amount": round(amount, 2),
        "reason": reason.strip(),
        "status": "SIMULATED",
    }
    if not event["reason"]:
        raise ValueError("reason must contain at least 10 non-whitespace characters")
    refund_events.append(event)
    logger.info("Created simulated refund %s", event["refund_id"])
    return event


if __name__ == "__main__":
    # FastMCP defaults to STDIO. Never print application output to stdout.
    mcp.run(transport="stdio")
