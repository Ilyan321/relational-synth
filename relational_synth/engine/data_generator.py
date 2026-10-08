import random
from typing import Any, Dict, List, Optional, Set
from faker import Faker
import re
from relational_synth.parser.schema_model import Schema, Table, Column, ColumnType, ForeignKey
from relational_synth.engine.semantic_rules import SemanticRules

class DataGeneratorError(Exception):
    """Custom exception for data generation errors."""
    pass

class DataGenerator:
    def __init__(self, schema: Schema, seed: Optional[int] = None):
        self.schema = schema
        self.faker = Faker()
        if seed is not None:
            self.faker.seed_instance(seed)
            random.seed(seed)

        self.semantic_rules = SemanticRules(self.faker)

        # State: Stores generated rows for each table.
        # Structure: { table_name: [ { col1: val1, col2: val2 }, ... ] }
        self.generated_data: Dict[str, List[Dict[str, Any]]] = {}

        # State: Cache of generated values for columns with UNIQUE constraint to prevent collisions
        # Structure: { (table_name, col_name): set(seen_values) }
        self.unique_cache: Dict[tuple[str, str], Set[Any]] = {}

        # State: Map of SERIAL counters for each table and column
        # Structure: { (table_name, col_name): current_counter }
        self.serial_counters: Dict[tuple[str, str], int] = {}

    def clear(self):
        """Clears previously generated data and cache states."""
        self.generated_data.clear()
        self.unique_cache.clear()
        self.serial_counters.clear()

    def generate_all(self, rows_per_table: int = 1000) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generates interconnected synthetic data for all tables in the schema
        respecting the topological insertion order and referential integrity.
        """
        self.clear()

        for table_name in self.schema.topological_order:
            table = self.schema.tables[table_name]
            self.generate_table(table, rows_per_table)

        return self.generated_data

    def generate_table(self, table: Table, row_count: int) -> List[Dict[str, Any]]:
        """Generates mock rows for a single table."""
        rows = []
        self.generated_data[table.name] = rows

        # Pre-cache generator functions for each column to improve performance in loops
        generators = {}
        for col in table.columns:
            generators[col.name] = self.semantic_rules.get_generator_for_column(col)

            # Initialize unique cache if needed
            if col.is_unique or col.is_primary_key:
                self.unique_cache[(table.name, col.name)] = set()

            # Initialize serial counter if it's a SERIAL type
            if col.data_type in (ColumnType.SERIAL, ColumnType.BIGSERIAL, ColumnType.SMALLSERIAL):
                self.serial_counters[(table.name, col.name)] = 1

        # We keep track of how many rows we generated
        for _ in range(row_count):
            row = self._generate_row(table, generators)
            rows.append(row)

        return rows

    def _generate_row(self, table: Table, generators: Dict[str, Any]) -> Dict[str, Any]:
        row = {}

        # Create a set of columns to process. We must process foreign key columns
        # and serial/unique columns with specific care.
        for col in table.columns:
            # 1. Handle SERIAL/Auto-increment types
            if col.data_type in (ColumnType.SERIAL, ColumnType.BIGSERIAL, ColumnType.SMALLSERIAL):
                counter_key = (table.name, col.name)
                val = self.serial_counters[counter_key]
                self.serial_counters[counter_key] += 1
                row[col.name] = val
                # Add to unique cache
                if col.is_unique or col.is_primary_key:
                    self.unique_cache[(table.name, col.name)].add(val)
                continue

            # 2. Handle Foreign Keys (Referential Integrity)
            # Find if this column has a foreign key constraint
            fk_constraint = next((fk for fk in table.foreign_keys if fk.column_name == col.name), None)
            if fk_constraint:
                row[col.name] = self._generate_fk_value(table, col, fk_constraint)
                continue

            # 3. Handle standard semantic generation with UNIQUE & CHECK constraint enforcement
            row[col.name] = self._generate_constrained_value(table, col, generators[col.name])

        return row

    def _generate_fk_value(self, table: Table, col: Column, fk: ForeignKey) -> Any:
        """Samples a valid primary key from the referenced parent table."""
        parent_table_name = fk.referenced_table
        parent_col_name = fk.referenced_column

        if parent_table_name not in self.generated_data or not self.generated_data[parent_table_name]:
            if col.is_nullable:
                return None
            else:
                raise DataGeneratorError(
                    f"Foreign key in table '{table.name}.{col.name}' references parent '{parent_table_name}' which has no generated data."
                )

        # Sample from already generated parent rows
        parent_rows = self.generated_data[parent_table_name]
        parent_row = random.choice(parent_rows)

        # If no specific referenced column was parsed, assume parent primary key
        ref_col = parent_col_name
        if not ref_col:
            parent_table_obj = self.schema.tables.get(parent_table_name)
            if parent_table_obj and parent_table_obj.primary_key:
                ref_col = parent_table_obj.primary_key[0] # Take first PK
            else:
                # Fallback to first column
                ref_col = list(parent_row.keys())[0]

        val = parent_row.get(ref_col)

        # If the foreign key is also unique, we must ensure we don't duplicate it
        if col.is_unique or col.is_primary_key:
            cache_key = (table.name, col.name)
            seen = self.unique_cache[cache_key]

            # If all parent keys are already used and it's nullable, return None
            # Otherwise we'll try to find a unused parent key
            unused_parent_keys = [r.get(ref_col) for r in parent_rows if r.get(ref_col) not in seen]
            if not unused_parent_keys:
                if col.is_nullable:
                    return None
                else:
                    raise DataGeneratorError(
                        f"Cannot enforce UNIQUE constraint on Foreign Key '{table.name}.{col.name}': All parent keys are already used."
                    )
            val = random.choice(unused_parent_keys)
            seen.add(val)

        return val

    def _generate_constrained_value(self, table: Table, col: Column, base_generator: Any) -> Any:
        """Generates a value, enforcing UNIQUE, CHECK, and NULL constraints with retries."""
        cache_key = (table.name, col.name)
        seen = self.unique_cache.get(cache_key)

        # Handle nullable columns: sample standard null percentage (e.g. 10% nulls)
        if col.is_nullable and not col.is_primary_key and not col.is_unique:
            if random.random() < 0.10: # 10% Null rate
                return None

        max_attempts = 1000
        for _ in range(max_attempts):
            val = base_generator()

            # Truncate string if column has max_length
            if col.max_length and isinstance(val, str):
                val = val[:col.max_length]

            # Enforce CHECK constraint
            if col.check_constraint:
                if not self._passes_check_constraint(col.name, val, col.check_constraint):
                    continue

            # Enforce UNIQUE constraint
            if seen is not None:
                if val in seen:
                    continue
                seen.add(val)

            return val

        # If we failed to generate after 1000 retries, raise error or return a fallback
        raise DataGeneratorError(
            f"Failed to generate unique/valid value for column '{table.name}.{col.name}' after {max_attempts} attempts."
        )

    def _strip_outer_parentheses(self, s: str) -> str:
        s = s.strip()
        while s.startswith('(') and s.endswith(')'):
            # Verify that the first and last parenthesis actually match each other
            depth = 0
            matching = True
            for i, char in enumerate(s):
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                    if depth == 0 and i < len(s) - 1:
                        # Parenthesis closed before the end of the string
                        matching = False
                        break
            if matching:
                s = s[1:-1].strip()
            else:
                break
        return s

    def _passes_check_constraint(self, col_name: str, val: Any, check_expr: str) -> bool:
        """Robust checks for simple CHECK constraints (e.g. age >= 18 or balance > 0)."""
        expr = self._strip_outer_parentheses(check_expr)

        # Match standard forms like: column_name > 10, column_name >= 18, column_name IS NOT NULL
        # 1. Inequality comparisons
        match = re.match(rf'^{re.escape(col_name)}\s*(>=|<=|>|<|=)\s*([-\d\.]+)', expr, re.IGNORECASE)
        if match:
            op, limit_str = match.groups()
            try:
                limit = float(limit_str) if '.' in limit_str else int(limit_str)
                v = float(val) if isinstance(val, (int, float, str)) else val
                if op == '>=': return v >= limit
                elif op == '<=': return v <= limit
                elif op == '>': return v > limit
                elif op == '<': return v < limit
                elif op == '=': return v == limit
            except (ValueError, TypeError):
                pass

        # 2. String check or IN list
        # E.g. status IN ('active', 'inactive')
        match_in = re.match(rf'^{re.escape(col_name)}\s+IN\s*\((.*?)\)', expr, re.IGNORECASE)
        if match_in:
            elements_str = match_in.group(1)
            # Parse elements, strip quotes
            allowed = [e.strip("'\" ") for e in elements_str.split(',')]
            return str(val) in allowed

        # Fallback: if we cannot parse it, assume true so we don't hang, or raise warning
        return True
