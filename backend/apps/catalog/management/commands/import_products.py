import hashlib
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.catalog.product_import_services import import_reviewed_products
from scripts.smartlinks_products import write_json


class Command(BaseCommand):
    help = "Import reviewed JSON as unpublished zero-stock product drafts; existing SKUs are skipped."

    def add_arguments(self, parser):
        parser.add_argument("input", type=Path, help="Schema version 1 reviewed product JSON.")
        parser.add_argument("--actor", required=True, help="Email of the active staff user approving this import.")
        parser.add_argument("--image-root", type=Path, help="Explicit root for relative local image paths; no downloads.")
        parser.add_argument("--dry-run", action="store_true", help="Validate all rows without persisting database records or images.")
        parser.add_argument("--report", type=Path, help="New JSON report path; defaults to INPUT.import-report.json.")

    def handle(self, *args, **options):
        input_path = options["input"].resolve()
        report_path = (options["report"] or input_path.with_name(input_path.name + ".import-report.json")).resolve()
        if report_path == input_path:
            raise CommandError("The report must not overwrite the reviewed input.")
        if report_path.exists():
            raise CommandError("The report already exists; choose a new --report path.")
        # Verify report access before starting any catalog writes.
        try:
            write_json(report_path, {"status": "started", "dry_run": options["dry_run"], "rows": []})
            raw = input_path.read_bytes()
            batch = json.loads(raw.decode("utf-8-sig"))
            actor = get_user_model().objects.filter(email__iexact=options["actor"].strip()).first()
            if actor is None:
                raise CommandError("The --actor email must identify an existing active staff user.")
            report = import_reviewed_products(
                batch=batch, actor=actor, image_root=options["image_root"], dry_run=options["dry_run"],
                metadata={"input_sha256": hashlib.sha256(raw).hexdigest()},
            )
        except (ValueError, OSError, PermissionDenied, ValidationError, CommandError) as exc:
            try:
                write_json(report_path, {"status": "failed", "error": str(exc)}, overwrite=True)
            except (ValueError, OSError):
                self.stderr.write("Could not save the failure report.")
            raise CommandError(str(exc)) from exc
        try:
            write_json(report_path, report, overwrite=True)
        except (ValueError, OSError) as exc:
            raise CommandError(f"Import finished but saving the report failed: {exc}. Rerunning is safe; existing SKUs are skipped.") from exc
        for row in report["rows"]:
            if row["status"] == "error":
                self.stderr.write(f"Row {row['row']} ({row['sku']}): {row['errors']}")
        counts = report["counts"]
        self.stdout.write(
            f"Created {counts['created']}; validated {counts['validated']}; skipped {counts['skipped']}; "
            f"errors {counts['error']}. Report: {report_path}"
        )
        if counts["error"]:
            raise CommandError("Some rows failed; successful imports were retained. Review the report before rerunning.")
