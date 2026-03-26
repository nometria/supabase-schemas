"""CLI entry point for supabase-schemas."""
import sys
import os
import argparse

from .schema_manager import (
    create_app_schema,
    drop_app_schema,
    list_app_schemas,
    run_migrations,
    schema_exists,
)


def main():
    parser = argparse.ArgumentParser(
        prog="supabase-schemas",
        description="Per-tenant PostgreSQL schema manager for Supabase",
    )
    parser.add_argument(
        "command",
        choices=["create", "drop", "list", "migrate"],
        help="Command to run",
    )
    parser.add_argument("tenant_id", nargs="?", help="Tenant ID")
    parser.add_argument("--migrations-dir", default="./migrations", help="Path to migrations directory")
    parser.add_argument("--force", action="store_true", help="Force drop without confirmation")
    parser.add_argument("--details", action="store_true", help="Show extra details in list")

    args = parser.parse_args()

    if args.command == "create":
        if not args.tenant_id:
            print("Error: tenant_id required for create", file=sys.stderr)
            sys.exit(1)
        schema_name = create_app_schema(args.tenant_id)
        print(f"Created schema for tenant: {args.tenant_id} (schema: {schema_name})")

    elif args.command == "drop":
        if not args.tenant_id:
            print("Error: tenant_id required for drop", file=sys.stderr)
            sys.exit(1)
        if not args.force:
            confirm = input(f"Drop schema for '{args.tenant_id}'? [y/N] ")
            if confirm.lower() != "y":
                print("Aborted.")
                sys.exit(0)
        drop_app_schema(args.tenant_id)
        print(f"Dropped schema for tenant: {args.tenant_id}")

    elif args.command == "list":
        schemas = list_app_schemas()
        if not schemas:
            print("No tenant schemas found.")
        else:
            for s in schemas:
                print(f"  {s}")

    elif args.command == "migrate":
        if not args.tenant_id:
            print("Error: tenant_id required for migrate", file=sys.stderr)
            sys.exit(1)
        applied = run_migrations(args.tenant_id, args.migrations_dir)
        if applied:
            print(f"Applied {len(applied)} migration(s) for tenant: {args.tenant_id}")
        else:
            print("No new migrations to apply.")


if __name__ == "__main__":
    main()
