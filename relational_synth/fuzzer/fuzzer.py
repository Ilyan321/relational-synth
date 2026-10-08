import json
import csv
import io
import re
from typing import Dict, List, Any
from relational_synth.parser.schema_model import Schema
from relational_synth.engine.data_generator import DataGenerator

class Fuzzer:
    def __init__(self, schema: Schema, generator: DataGenerator):
        self.schema = schema
        self.generator = generator

    def generate_positive_seed(self, rows_per_table: int = 100) -> Dict[str, List[Dict[str, Any]]]:
        """Generates clean, compliant mock data."""
        return self.generator.generate_all(rows_per_table)

    def to_sql(self, data: Dict[str, List[Dict[str, Any]]]) -> str:
        """Converts generated data to a SQL INSERT script, respecting topological order."""
        sql_lines = []

        # Follow topological order to ensure parents are inserted before children
        for table_name in self.schema.topological_order:
            rows = data.get(table_name, [])
            if not rows:
                continue

            sql_lines.append(f"-- Data for table: {table_name}")
            for row in rows:
                cols = ", ".join(row.keys())
                vals = []
                for v in row.values():
                    if v is None:
                        vals.append("NULL")
                    elif isinstance(v, (int, float)):
                        vals.append(str(v))
                    elif isinstance(v, bool):
                        vals.append("TRUE" if v else "FALSE")
                    else:
                        # Escape single quotes for SQL
                        escaped = str(v).replace("'", "''")
                        vals.append(f"'{escaped}'")

                vals_str = ", ".join(vals)
                sql_lines.append(f"INSERT INTO {table_name} ({cols}) VALUES ({vals_str});")
            sql_lines.append("") # Empty line between tables

        return "\n".join(sql_lines)

    def generate_negative_fuzz(self, rows_per_table: int = 10) -> str:
        """Generates deliberate violation records for testing database defenses."""
        fuzz_sql = []

        for table_name in self.schema.topological_order:
            table = self.schema.tables[table_name]
            fuzz_sql.append(f"-- Fuzz test cases for table: {table_name}")

            for col in table.columns:
                # 1. NULL in NOT NULL columns
                if not col.is_nullable:
                    fuzz_sql.append(f"-- Violation: NULL in NOT NULL column '{col.name}'")
                    row = self._generate_mostly_valid_row(table)
                    row[col.name] = None
                    fuzz_sql.append(self._row_to_insert(table_name, row))

                # 2. CHECK constraint violations
                if col.check_constraint:
                    fuzz_sql.append(f"-- Violation: CHECK constraint violation on '{col.name}' ({col.check_constraint})")
                    row = self._generate_mostly_valid_row(table)
                    row[col.name] = self._generate_violating_value(col)
                    fuzz_sql.append(self._row_to_insert(table_name, row))

                # 3. UNIQUE constraint violations
                if (col.is_unique or col.is_primary_key) and table_name in self.generator.generated_data:
                    existing_rows = self.generator.generated_data[table_name]
                    if existing_rows:
                        fuzz_sql.append(f"-- Violation: Duplicate value in UNIQUE column '{col.name}'")
                        row = self._generate_mostly_valid_row(table)
                        row[col.name] = existing_rows[0][col.name]
                        fuzz_sql.append(self._row_to_insert(table_name, row))

            # 4. Orphan Foreign Keys
            for fk in table.foreign_keys:
                fuzz_sql.append(f"-- Violation: Orphan Foreign Key reference on '{fk.column_name}'")
                row = self._generate_mostly_valid_row(table)
                # Use an obviously non-existent ID (assuming positive IDs)
                row[fk.column_name] = 99999999
                fuzz_sql.append(self._row_to_insert(table_name, row))

            fuzz_sql.append("")

        return "\n".join(fuzz_sql)

    def _generate_mostly_valid_row(self, table) -> Dict[str, Any]:
        """Generates a valid row that we can then mutate for fuzzing."""
        # We reuse the generator's row generation logic but without state storage
        # We pre-cache generators for the table
        generators = {col.name: self.generator.semantic_rules.get_generator_for_column(col) for col in table.columns}
        return self.generator._generate_row(table, generators)

    def _generate_violating_value(self, col) -> Any:
        """Tries to create a value that violates a CHECK constraint."""
        expr = self.generator._strip_outer_parentheses(col.check_constraint)

        # Simple numeric violations
        match = re.search(rf'{re.escape(col.name)}\s*(>=|>|<=|<|=)\s*([-\d\.]+)', expr, re.IGNORECASE)
        if match:
            op, limit_str = match.groups()
            limit = float(limit_str) if '.' in limit_str else int(limit_str)
            if op in ('>=', '>'): return limit - 1
            if op in ('<=', '<'): return limit + 1
            if op == '=': return limit + 1

        # Enum violations
        match_in = re.search(rf'{re.escape(col.name)}\s+IN\s*\((.*?)\)', expr, re.IGNORECASE)
        if match_in:
            return "invalid_enum_value_999"

        return "invalid_fuzz_val"

    def _row_to_insert(self, table_name: str, row: Dict[str, Any]) -> str:
        cols = ", ".join(row.keys())
        vals = []
        for v in row.values():
            if v is None: vals.append("NULL")
            elif isinstance(v, (int, float)): vals.append(str(v))
            elif isinstance(v, bool): vals.append("TRUE" if v else "FALSE")
            else: vals.append(f"'{str(v).replace("'", "''")}'")
        return f"INSERT INTO {table_name} ({cols}) VALUES ({', '.join(vals)});"
