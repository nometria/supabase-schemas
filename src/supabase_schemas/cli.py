"""CLI entry point for supabase-schemas."""
import sys
import argparse

from .schema_manager import (
    create_app_schema,
    drop_app_schema,
    list_app_schemas,
    run_migrations,
    clone_schema,
    export_schema,
)


def main():
    parser = argparse.ArgumentParser(
        prog="supabase-schemas",
        description="Per-tenant PostgreSQL schema manager for Supabase",
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # create
    p_create = sub.add_parser("create", help="Create a new tenant schema")
    p_create.add_argument("tenant_id", help="Tenant ID")
    p_create.add_argument("--migrations-dir", default="./migrations", help="Path to migrations directory")

    # drop
    p_drop = sub.add_parser("drop", help="Drop a tenant schema")
    p_drop.add_argument("tenant_id", help="Tenant ID")
    p_drop.add_argument("--force", action="store_true", help="Force drop without confirmation")

    # list
    p_list = sub.add_parser("list", help="List all tenant schemas")
    p_list.add_argument("--details", action="store_true", help="Show extra details in list")

    # migrate
    p_migrate = sub.add_parser("migrate", help="Run migrations for a tenant")
    p_migrate.add_argument("tenant_id", help="Tenant ID")
    p_migrate.add_argument("--migrations-dir", default="./migrations", help="Path to migrations directory")

    # clone
    p_clone = sub.add_parser("clone", help="Clone schema structure from one tenant to another (no data)")
    p_clone.add_argument("source_schema", help="Source tenant ID to clone from")
    p_clone.add_argument("target_schema", help="Target tenant ID to clone into")

    # export
    p_export = sub.add_parser("export", help="Export a tenant's data to JSON")
    p_export.add_argument("schema_name", help="Tenant ID to export")
    p_export.add_argument("--output", "-o", help="Output file path (default: stdout)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "create":
        schema_name = create_app_schema(args.tenant_id)
        print(f"Created schema for tenant: {args.tenant_id} (schema: {schema_name})")

    elif args.command == "drop":
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
        applied = run_migrations(args.tenant_id, args.migrations_dir)
        if applied:
            print(f"Applied {len(applied)} migration(s) for tenant: {args.tenant_id}")
        else:
            print("No new migrations to apply.")

    elif args.command == "clone":
        target = clone_schema(args.source_schema, args.target_schema)
        print(f"Cloned into schema: {target}")

    elif args.command == "export":
        export_schema(args.schema_name, output_path=args.output)


if __name__ == "__main__":
    main()
