from task3_llm_guardrail.redaction import redact_complete_text, StreamingRedactor

def test_redacts_patterns():
    text = "Contact jane@example.com, SSN 123-45-6789, card 4111 1111 1111 1111."
    result = redact_complete_text(text)
    assert "jane@example.com" not in result
    assert "123-45-6789" not in result
    assert "4111 1111 1111 1111" not in result
    assert result.count("[REDACTED]") == 3

def test_redacts_across_chunks():
    r = StreamingRedactor(overlap=40)
    output = r.push("A" * 50 + " jane@exa")
    output += r.push("mple.com" + "B" * 50)
    output += r.finish()
    assert "jane@example.com" not in output
    assert "[REDACTED]" in output
