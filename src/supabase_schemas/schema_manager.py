#!/usr/bin/env python3
"""
supabase-schemas — per-tenant PostgreSQL schema manager for Supabase.

Manages isolated schemas within a single Supabase instance.
Each tenant gets its own schema (app_<id>) while sharing auth.users.
All schemas are tracked and can be created, dropped, listed, or migrated.

Usage:
    python schema_manager.py create <tenant_id> [--migrations-dir <path>]
    python schema_manager.py drop <tenant_id> [--force]
    python schema_manager.py list [--details]
    python schema_manager.py migrate <tenant_id> --migrations-dir <path>
"""

import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
import re

# Try to import psycopg2, but don't fail if not available
try:
    import psycopg2
    from psycopg2 import sql
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
    sql = None

# Database connection from environment
# This should point to the existing Supabase PostgreSQL instance
# Default is local Supabase docker setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres.your-tenant-id:your-super-secret-and-long-postgres-password@localhost:5432/postgres")


def parse_database_url(url: str) -> Dict[str, Any]:
    """Parse PostgreSQL connection URL into components."""
    # Format: postgresql://user:password@host:port/database
    # Also support postgres:// prefix
    url = url.replace("postgres://", "postgresql://")
    pattern = r'postgresql://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+):?(?P<port>\d+)?/(?P<database>[^?]+)'
    match = re.match(pattern, url)
    if match:
        result = match.groupdict()
        result['port'] = result['port'] or '5432'
        return result
    # Fallback defaults for local Supabase
    return {
        'user': 'postgres.your-tenant-id',
        'password': 'your-super-secret-and-long-postgres-password',
        'host': 'localhost',
        'port': '5432',
        'database': 'postgres'
    }


def get_connection():
    """Get database connection to existing Supabase instance."""
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 not installed. Run: pip install psycopg2-binary")
    
    params = parse_database_url(DATABASE_URL)
    return psycopg2.connect(
        host=params['host'],
        port=params['port'],
        user=params['user'],
        password=params['password'],
        database=params['database']
    )


def sanitize_schema_name(app_id: str) -> str:
    """
    Convert app_id to a valid PostgreSQL schema name.
    Schema names must start with a letter or underscore and contain only
    letters, digits, and underscores.
    """
    # Replace hyphens with underscores
    schema = app_id.replace('-', '_')
    # Ensure it starts with a letter or underscore
    if schema and not (schema[0].isalpha() or schema[0] == '_'):
        schema = 'app_' + schema
    # Remove any invalid characters
    schema = re.sub(r'[^a-zA-Z0-9_]', '', schema)
    # Prefix with 'app_' to avoid conflicts with reserved names
    if not schema.startswith('app_'):
        schema = 'app_' + schema
    return schema.lower()


def create_app_schema(app_id: str, conn=None) -> str:
    """
    Create a new schema for an app within the existing Supabase instance.
    Uses public.ensure_schema_exposed(schema_name) to create the schema and grant
    privileges in one DB call; then creates _migrations table and users view in the schema.
    
    Args:
        app_id: The application ID
        conn: Optional existing database connection
    
    Returns:
        The schema name created
    """
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 not installed. Run: pip install psycopg2-binary")
    
    should_close = conn is None
    if conn is None:
        conn = get_connection()
    
    schema_name = sanitize_schema_name(app_id)
    
    try:
        with conn.cursor() as cur:
            # Create schema and grant privileges in one call (main DB function)
            cur.execute("SELECT public.ensure_schema_exposed(%s)", (schema_name,))
            
            # Create migrations tracking table in the schema
            cur.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS {}._migrations (
                    id SERIAL PRIMARY KEY,
                    migration_name TEXT NOT NULL UNIQUE,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """).format(sql.Identifier(schema_name)))
            
            # Create a view to access auth.users from the app schema
            # This allows apps to reference users without direct auth schema access
            # Using DO block to handle if auth.users doesn't exist
            cur.execute("""
                DO $$ 
                BEGIN
                    EXECUTE 'CREATE OR REPLACE VIEW ' || quote_ident(%s) || '.users AS 
                        SELECT id, email, created_at, updated_at, 
                               raw_user_meta_data->>''full_name'' as full_name,
                               raw_user_meta_data->>''role'' as role
                        FROM auth.users';
                    BEGIN
                        EXECUTE 'GRANT SELECT ON ' || quote_ident(%s) || '.users TO anon, authenticated, service_role';
                    EXCEPTION WHEN undefined_object THEN NULL;
                    END;
                EXCEPTION 
                    WHEN undefined_table THEN 
                        RAISE NOTICE 'auth.users table not found, skipping users view';
                    WHEN insufficient_privilege THEN
                        RAISE NOTICE 'Insufficient privileges to create users view';
                END $$;
            """, (schema_name, schema_name))
            
            conn.commit()
            print(f"✅ Created schema '{schema_name}' for app '{app_id}'")
            return schema_name
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Error creating schema: {e}")
        raise
    finally:
        if should_close:
            conn.close()


def drop_app_schema(app_id: str, conn=None) -> bool:
    """
    Drop an app's schema and all its objects from the Supabase instance.
    
    WARNING: This deletes all tables and data in the schema!
    
    Args:
        app_id: The application ID
        conn: Optional existing database connection
    
    Returns:
        True if successful
    """
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 not installed. Run: pip install psycopg2-binary")
    
    should_close = conn is None
    if conn is None:
        conn = get_connection()
    
    schema_name = sanitize_schema_name(app_id)
    
    try:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                sql.Identifier(schema_name)
            ))
            conn.commit()
            print(f"✅ Dropped schema '{schema_name}' for app '{app_id}'")
            return True
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Error dropping schema: {e}")
        raise
    finally:
        if should_close:
            conn.close()


def list_app_schemas(conn=None) -> List[str]:
    """
    List all app schemas in the Supabase database.
    
    Returns:
        List of schema names (those starting with 'app_')
    """
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 not installed. Run: pip install psycopg2-binary")
    
    should_close = conn is None
    if conn is None:
        conn = get_connection()
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name LIKE 'app_%'
                ORDER BY schema_name
            """)
            schemas = [row[0] for row in cur.fetchall()]
            return schemas
    finally:
        if should_close:
            conn.close()


def run_migrations(app_id: str, migrations_dir: str, conn=None) -> List[str]:
    """
    Run pending migrations for an app schema.
    
    Args:
        app_id: The application ID
        migrations_dir: Path to the migrations directory
        conn: Optional existing database connection
    
    Returns:
        List of applied migration names
    """
    should_close = conn is None
    if conn is None:
        conn = get_connection()
    
    schema_name = sanitize_schema_name(app_id)
    migrations_path = Path(migrations_dir)
    
    if not migrations_path.exists():
        print(f"⚠️ Migrations directory not found: {migrations_dir}")
        return []
    
    # Get list of migration files
    migration_files = sorted([
        f for f in migrations_path.glob("*.sql")
        if f.is_file()
    ])
    
    if not migration_files:
        print(f"ℹ️ No migration files found in {migrations_dir}")
        return []
    
    applied = []
    
    try:
        with conn.cursor() as cur:
            # Set search path to app schema
            cur.execute(sql.SQL("SET search_path TO {}, public").format(
                sql.Identifier(schema_name)
            ))
            
            # Get already applied migrations
            cur.execute(sql.SQL("""
                SELECT migration_name FROM {}._migrations
            """).format(sql.Identifier(schema_name)))
            applied_migrations = {row[0] for row in cur.fetchall()}
            
            for migration_file in migration_files:
                migration_name = migration_file.name
                
                if migration_name in applied_migrations:
                    print(f"  ⏭️ Skipping {migration_name} (already applied)")
                    continue
                
                print(f"  🔄 Applying {migration_name}...")
                
                # Read and execute migration
                migration_sql = migration_file.read_text()
                
                # Replace 'public.' with schema name for table references
                # This allows migrations written for public schema to work per-app
                migration_sql = migration_sql.replace('"public".', f'"{schema_name}".')
                
                try:
                    cur.execute(migration_sql)
                    
                    # Record the migration
                    cur.execute(sql.SQL("""
                        INSERT INTO {}._migrations (migration_name) VALUES (%s)
                    """).format(sql.Identifier(schema_name)), (migration_name,))
                    
                    conn.commit()
                    applied.append(migration_name)
                    print(f"  ✅ Applied {migration_name}")
                    
                except Exception as e:
                    conn.rollback()
                    print(f"  ❌ Failed to apply {migration_name}: {e}")
                    raise
            
            # Reset search path
            cur.execute("SET search_path TO public")
            
        return applied
        
    finally:
        if should_close:
            conn.close()


def get_schema_tables(app_id: str, conn=None) -> List[Dict[str, Any]]:
    """
    Get list of tables in an app schema.
    
    Args:
        app_id: The application ID
        conn: Optional existing database connection
    
    Returns:
        List of table info dictionaries
    """
    should_close = conn is None
    if conn is None:
        conn = get_connection()
    
    schema_name = sanitize_schema_name(app_id)
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name, 
                       (SELECT COUNT(*) FROM information_schema.columns 
                        WHERE table_schema = %s AND table_name = t.table_name) as column_count
                FROM information_schema.tables t
                WHERE table_schema = %s AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """, (schema_name, schema_name))
            
            tables = []
            for row in cur.fetchall():
                tables.append({
                    'name': row[0],
                    'columns': row[1]
                })
            return tables
    finally:
        if should_close:
            conn.close()


def schema_exists(app_id: str, conn=None) -> bool:
    """Check if a schema exists for the given app_id."""
    should_close = conn is None
    if conn is None:
        conn = get_connection()
    
    schema_name = sanitize_schema_name(app_id)
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.schemata 
                    WHERE schema_name = %s
                )
            """, (schema_name,))
            return cur.fetchone()[0]
    finally:
        if should_close:
            conn.close()


def clone_schema(source_id: str, target_id: str, conn=None) -> str:
    """
    Clone schema structure from one tenant to another.
    Copies tables, indexes, and constraints using CREATE TABLE ... (LIKE ... INCLUDING ALL).
    Does NOT copy data — only structure.

    Args:
        source_id: The source tenant ID to clone from
        target_id: The target tenant ID to clone into
        conn: Optional existing database connection

    Returns:
        The target schema name created
    """
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 not installed. Run: pip install psycopg2-binary")

    should_close = conn is None
    if conn is None:
        conn = get_connection()

    source_schema = sanitize_schema_name(source_id)
    target_schema = sanitize_schema_name(target_id)

    try:
        with conn.cursor() as cur:
            # Verify source schema exists
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.schemata
                    WHERE schema_name = %s
                )
            """, (source_schema,))
            if not cur.fetchone()[0]:
                raise ValueError(f"Source schema '{source_schema}' does not exist")

            # Create the target schema (with privileges via ensure_schema_exposed)
            cur.execute("SELECT public.ensure_schema_exposed(%s)", (target_schema,))

            # Create migrations tracking table in the target schema
            cur.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS {}._migrations (
                    id SERIAL PRIMARY KEY,
                    migration_name TEXT NOT NULL UNIQUE,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """).format(sql.Identifier(target_schema)))

            # Get all base tables from the source schema (excluding _migrations and views)
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                  AND table_name != '_migrations'
                ORDER BY table_name
            """, (source_schema,))
            tables = [row[0] for row in cur.fetchall()]

            for table_name in tables:
                cur.execute(sql.SQL(
                    "CREATE TABLE {}.{} (LIKE {}.{} INCLUDING ALL)"
                ).format(
                    sql.Identifier(target_schema),
                    sql.Identifier(table_name),
                    sql.Identifier(source_schema),
                    sql.Identifier(table_name),
                ))
                print(f"  Cloned table: {table_name}")

            # Recreate the auth.users view in the target schema
            cur.execute("""
                DO $$
                BEGIN
                    EXECUTE 'CREATE OR REPLACE VIEW ' || quote_ident(%s) || '.users AS
                        SELECT id, email, created_at, updated_at,
                               raw_user_meta_data->>''full_name'' as full_name,
                               raw_user_meta_data->>''role'' as role
                        FROM auth.users';
                    BEGIN
                        EXECUTE 'GRANT SELECT ON ' || quote_ident(%s) || '.users TO anon, authenticated, service_role';
                    EXCEPTION WHEN undefined_object THEN NULL;
                    END;
                EXCEPTION
                    WHEN undefined_table THEN
                        RAISE NOTICE 'auth.users table not found, skipping users view';
                    WHEN insufficient_privilege THEN
                        RAISE NOTICE 'Insufficient privileges to create users view';
                END $$;
            """, (target_schema, target_schema))

            conn.commit()
            print(f"Cloned schema '{source_schema}' -> '{target_schema}' ({len(tables)} tables, structure only)")
            return target_schema

    except Exception as e:
        conn.rollback()
        print(f"Error cloning schema: {e}")
        raise
    finally:
        if should_close:
            conn.close()


def export_schema(app_id: str, output_path: str = None, conn=None) -> Dict[str, list]:
    """
    Export all table data from a tenant's schema to JSON.

    Args:
        app_id: The application/tenant ID
        output_path: Optional file path to write JSON to. If None, returns data only.
        conn: Optional existing database connection

    Returns:
        Dictionary mapping table names to lists of row dicts: {"table_name": [rows], ...}
    """
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 not installed. Run: pip install psycopg2-binary")

    should_close = conn is None
    if conn is None:
        conn = get_connection()

    schema_name = sanitize_schema_name(app_id)

    try:
        with conn.cursor() as cur:
            # Verify schema exists
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.schemata
                    WHERE schema_name = %s
                )
            """, (schema_name,))
            if not cur.fetchone()[0]:
                raise ValueError(f"Schema '{schema_name}' does not exist")

            # Get all base tables (excluding internal _migrations table)
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                  AND table_name != '_migrations'
                ORDER BY table_name
            """, (schema_name,))
            tables = [row[0] for row in cur.fetchall()]

            result = {}
            for table_name in tables:
                # Get column names
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                """, (schema_name, table_name))
                columns = [row[0] for row in cur.fetchall()]

                # Fetch all rows
                cur.execute(sql.SQL("SELECT * FROM {}.{}").format(
                    sql.Identifier(schema_name),
                    sql.Identifier(table_name),
                ))
                rows = cur.fetchall()

                # Convert to list of dicts, serializing non-JSON-native types
                table_rows = []
                for row in rows:
                    row_dict = {}
                    for col, val in zip(columns, row):
                        # Convert non-serializable types to strings
                        if isinstance(val, (bytes, bytearray)):
                            row_dict[col] = val.hex()
                        else:
                            try:
                                json.dumps(val)
                                row_dict[col] = val
                            except (TypeError, ValueError):
                                row_dict[col] = str(val)
                    table_rows.append(row_dict)

                result[table_name] = table_rows
                print(f"  Exported {table_name}: {len(table_rows)} rows")

            # Write to file or stdout
            json_output = json.dumps(result, indent=2, default=str)
            if output_path:
                Path(output_path).write_text(json_output)
                print(f"Exported schema '{schema_name}' to {output_path}")
            else:
                print(json_output)

            print(f"Export complete: {len(tables)} tables")
            return result

    except Exception as e:
        print(f"Error exporting schema: {e}")
        raise
    finally:
        if should_close:
            conn.close()


def get_app_schema_name(app_id: str) -> str:
    """Get the schema name for an app ID."""
    return sanitize_schema_name(app_id)


# Export functions for use in generate_schema.py
__all__ = [
    'create_app_schema',
    'drop_app_schema',
    'list_app_schemas',
    'run_migrations',
    'get_schema_tables',
    'schema_exists',
    'get_app_schema_name',
    'sanitize_schema_name',
    'clone_schema',
    'export_schema',
    'get_connection',
]


def main():
    parser = argparse.ArgumentParser(
        description='Manage per-app database schemas for Nometria staging/production'
    )
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create a new app schema')
    create_parser.add_argument('app_id', help='Application ID')
    create_parser.add_argument('--migrations-dir', '-m', 
                              help='Path to migrations directory to apply after creation')
    
    # Drop command
    drop_parser = subparsers.add_parser('drop', help='Drop an app schema')
    drop_parser.add_argument('app_id', help='Application ID')
    drop_parser.add_argument('--force', '-f', action='store_true',
                            help='Skip confirmation prompt')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all app schemas')
    list_parser.add_argument('--details', '-d', action='store_true',
                            help='Show table details for each schema')
    
    # Migrate command
    migrate_parser = subparsers.add_parser('migrate', help='Run migrations for an app')
    migrate_parser.add_argument('app_id', help='Application ID')
    migrate_parser.add_argument('--migrations-dir', '-m', required=True,
                               help='Path to migrations directory')

    # Clone command
    clone_parser = subparsers.add_parser('clone', help='Clone schema structure from one tenant to another')
    clone_parser.add_argument('source_id', help='Source tenant ID to clone from')
    clone_parser.add_argument('target_id', help='Target tenant ID to clone into')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export tenant schema data to JSON')
    export_parser.add_argument('app_id', help='Application ID')
    export_parser.add_argument('--output', '-o', help='Output file path (default: stdout)')

    args = parser.parse_args()
    
    if args.command == 'create':
        schema_name = create_app_schema(args.app_id)
        print(f"Schema name: {schema_name}")
        
        if args.migrations_dir:
            print(f"\nRunning migrations from {args.migrations_dir}...")
            applied = run_migrations(args.app_id, args.migrations_dir)
            print(f"Applied {len(applied)} migrations")
            
    elif args.command == 'drop':
        if not args.force:
            confirm = input(f"Are you sure you want to drop schema for '{args.app_id}'? (y/N): ")
            if confirm.lower() != 'y':
                print("Cancelled")
                return
        drop_app_schema(args.app_id)
        
    elif args.command == 'list':
        schemas = list_app_schemas()
        if not schemas:
            print("No app schemas found")
        else:
            print(f"Found {len(schemas)} app schemas:")
            for schema in schemas:
                print(f"  - {schema}")
                if args.details:
                    # Extract app_id from schema name (remove 'app_' prefix)
                    app_id = schema[4:] if schema.startswith('app_') else schema
                    tables = get_schema_tables(app_id)
                    for table in tables:
                        print(f"      • {table['name']} ({table['columns']} columns)")
                        
    elif args.command == 'migrate':
        if not schema_exists(args.app_id):
            print(f"Schema for '{args.app_id}' does not exist. Creating...")
            create_app_schema(args.app_id)

        print(f"Running migrations from {args.migrations_dir}...")
        applied = run_migrations(args.app_id, args.migrations_dir)
        if applied:
            print(f"Applied {len(applied)} migrations: {', '.join(applied)}")
        else:
            print("No new migrations to apply")

    elif args.command == 'clone':
        target_schema = clone_schema(args.source_id, args.target_id)
        print(f"Target schema: {target_schema}")

    elif args.command == 'export':
        export_schema(args.app_id, output_path=args.output)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
