from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_productimage"),
    ]

    operations = [
        TrigramExtension(),
        # Django 5.2 renders an expression OpClass inside a single pair of
        # parentheses, which PostgreSQL rejects. The extra pair is required.
        migrations.RunSQL(
            'CREATE INDEX product_name_trgm_idx ON catalog_product USING GIN ((UPPER("name")) gin_trgm_ops)',
            'DROP INDEX product_name_trgm_idx',
        ),
        migrations.RunSQL(
            'CREATE INDEX product_sku_trgm_idx ON catalog_product USING GIN ((UPPER("sku")) gin_trgm_ops)',
            'DROP INDEX product_sku_trgm_idx',
        ),
    ]
