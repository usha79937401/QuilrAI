import pytest
from task1_mcp_server.server import validate_customer_id

def test_valid_customer_id():
    assert validate_customer_id("CUST-12345") == "CUST-12345"

@pytest.mark.parametrize("value", ["cust-12345", "CUST-1234", "CUST-123456", "12345", "CUST-ABCDE"])
def test_invalid_customer_id(value):
    with pytest.raises(ValueError):
        validate_customer_id(value)
