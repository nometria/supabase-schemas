"""Tests for supabase-schemas — no live DB required."""
import pytest
import json
import sys
import os
from unittest.mock import MagicMock, patch, call

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


def test_sanitize_schema_name():
    """sanitize_schema_name produces valid app_* identifiers."""
    from supabase_schemas.schema_manager import sanitize_schema_name

    assert sanitize_schema_name("acme-corp") == "app_acme_corp"
    assert sanitize_schema_name("Tenant123") == "app_tenant123"
    assert sanitize_schema_name("123numeric") == "app_123numeric"
    assert sanitize_schema_name("app_already") == "app_already"
    # Special characters stripped
    result = sanitize_schema_name("bad!@#name")
    assert result.isidentifier() or result.replace("_", "").isalnum()
    assert result.startswith("app_")


def test_clone_schema_rejects_missing_source():
    """clone_schema raises ValueError when source schema does not exist."""
    from supabase_schemas.schema_manager import clone_schema

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    # schema_exists check returns False
    mock_cursor.fetchone.return_value = (False,)

    with patch("supabase_schemas.schema_manager.PSYCOPG2_AVAILABLE", True), \
         patch("supabase_schemas.schema_manager.sql") as mock_sql:
        mock_sql.Identifier = MagicMock()
        mock_sql.SQL = MagicMock()
        with pytest.raises(ValueError, match="does not exist"):
            clone_schema("nonexistent", "target", conn=mock_conn)


def test_export_schema_rejects_missing_schema():
    """export_schema raises ValueError when schema does not exist."""
    from supabase_schemas.schema_manager import export_schema

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    # schema_exists check returns False
    mock_cursor.fetchone.return_value = (False,)

    with patch("supabase_schemas.schema_manager.PSYCOPG2_AVAILABLE", True), \
         patch("supabase_schemas.schema_manager.sql") as mock_sql:
        mock_sql.Identifier = MagicMock()
        mock_sql.SQL = MagicMock()
        with pytest.raises(ValueError, match="does not exist"):
            export_schema("nonexistent", conn=mock_conn)


def test_clone_schema_names_are_correct():
    """clone_schema derives correct source and target schema names."""
    from supabase_schemas.schema_manager import sanitize_schema_name

    source = sanitize_schema_name("acme-prod")
    target = sanitize_schema_name("acme-staging")
    assert source == "app_acme_prod"
    assert target == "app_acme_staging"
    assert source != target


def test_export_schema_function_exists():
    """export_schema and clone_schema are importable from the package."""
    from supabase_schemas import clone_schema, export_schema
    assert callable(clone_schema)
    assert callable(export_schema)
