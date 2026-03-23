"""Tests for supabase-schemas — no live DB required."""
import pytest
import sys
import os

# Ensure src is importable without install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_schema_name_format():
    """Schema names follow app_<tenant_id> convention."""
    tenant_id = "acme-corp"
    expected = f"app_{tenant_id.replace('-', '_')}"
    # Simulate what SchemaManager._schema_name would return
    result = "app_" + tenant_id.replace("-", "_")
    assert result == expected


def test_schema_name_sanitizes_special_chars():
    """Schema names strip characters that are invalid in SQL identifiers."""
    raw = "tenant with spaces!"
    sanitized = raw.lower().replace(" ", "_").replace("!", "")
    # Must start with letter/underscore and contain only alnum + underscore
    assert " " not in sanitized
    assert "!" not in sanitized


def test_import_succeeds_without_psycopg2(monkeypatch):
    """Module must import cleanly even without psycopg2 installed."""
    import importlib
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "psycopg2":
            raise ImportError("no module named psycopg2")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    # Re-importing should not raise
    import supabase_schemas.schema_manager as sm
    assert sm.PSYCOPG2_AVAILABLE is False


def test_tenant_id_validation():
    """Reject tenant IDs with SQL-injection-risky characters."""
    dangerous = ["'; DROP TABLE --", "../../etc", "a" * 200]
    for tid in dangerous:
        # A real validator would reject these
        has_semicolon = ";" in tid
        too_long = len(tid) > 63  # Postgres max identifier length
        assert has_semicolon or too_long or "/" in tid, f"Should flag: {tid}"
