import sqlparse
import networkx as nx
from typing import List, Dict, Optional
import re
from relational_synth.parser.schema_model import Schema, Table, Column, ForeignKey, ColumnType

class DDLParserError(Exception):
    """Custom exception for DDL parsing errors."""
    pass

class DDLParser:
    def __init__(self):
        self.schema = Schema()

    def parse_ddl_from_file(self, file_path: str) -> Schema:
        with open(file_path, 'r') as f:
            ddl_content = f.read()
        return self.parse_ddl(ddl_content)

    def parse_ddl(self, ddl_content: str) -> Schema:
        self.schema = Schema(raw_ddl=ddl_content)
        parsed = sqlparse.parse(ddl_content)

        for statement in parsed:
            # Find the first non-whitespace, non-comment token
            first_token = None
            for token in statement.tokens:
                if not token.is_whitespace and not isinstance(token, sqlparse.sql.Comment):
                    first_token = token
                    break

            if first_token and first_token.value.upper() == 'CREATE':
                is_table = False
                for token in statement.tokens:
                    if token.value.upper() == 'TABLE':
                        is_table = True
                        break
                if is_table:
                    self._parse_create_table(statement)

        self._build_and_sort_dag()
        return self.schema

    def _flatten_except_parenthesis(self, token: sqlparse.sql.Token) -> List[sqlparse.sql.Token]:
        if isinstance(token, sqlparse.sql.Parenthesis):
            return [token]
        if hasattr(token, 'tokens'):
            res = []
            for t in token.tokens:
                res.extend(self._flatten_except_parenthesis(t))
            return res
        return [token]

    def _parse_create_table(self, statement: sqlparse.sql.Statement):
        # Filter out whitespace and comments from top-level statement tokens
        tokens = [t for t in statement.tokens if not t.is_whitespace and not isinstance(t, sqlparse.sql.Comment)]

        # Find 'TABLE' keyword
        table_idx = -1
        for i, token in enumerate(tokens):
            if token.value.upper() == 'TABLE':
                table_idx = i
                break

        if table_idx == -1:
            raise DDLParserError("Not a CREATE TABLE statement")

        # Scan forward for table name, skipping 'IF NOT EXISTS' or 'IF', 'NOT', 'EXISTS'
        table_name_token = None
        for token in tokens[table_idx + 1:]:
            token_val_upper = token.value.upper()
            if token_val_upper in ('IF', 'NOT', 'EXISTS', 'IF NOT EXISTS'):
                continue
            # Accept Identifier, Name, or standard Token
            if isinstance(token, (sqlparse.sql.Identifier, sqlparse.sql.Token)) or token.ttype in (sqlparse.tokens.Name, sqlparse.tokens.String.Symbol):
                table_name_token = token
                break

        if not table_name_token:
            raise DDLParserError(f"Could not find table name in CREATE TABLE statement: {statement}")

        table_name = table_name_token.value.strip('"` ').lower()
        # Handle cases where Identifier contains the name
        if hasattr(table_name_token, 'get_real_name'):
            table_name = table_name_token.get_real_name().lower()

        table = Table(name=table_name)

        # Find the parenthesis containing column and constraint definitions
        paren_group = None
        for token in statement.tokens:
            if isinstance(token, sqlparse.sql.Parenthesis):
                paren_group = token
                break

        if not paren_group:
            raise DDLParserError(f"No column definitions found for table {table_name}")

        # Flatten everything inside the parenthesis except the inner parentheses
        flat_tokens = []
        for token in paren_group.tokens[1:-1]: # Skip the outer '(' and ')'
            flat_tokens.extend(self._flatten_except_parenthesis(token))

        # Filter out whitespace
        flat_tokens = [t for t in flat_tokens if not t.is_whitespace]

        # Split tokens by top-level commas (outside any parenthesis)
        definitions = []
        current_def = []
        for token in flat_tokens:
            if token.value == ',':
                if current_def:
                    definitions.append(current_def)
                    current_def = []
            else:
                current_def.append(token)
        if current_def:
            definitions.append(current_def)

        # Process each definition
        for clean_items in definitions:
            if not clean_items:
                continue

            # Check if this is a table-level constraint
            first_val = clean_items[0].value.upper()
            if first_val in ('CONSTRAINT', 'PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK'):
                self._parse_table_level_constraint(table, clean_items)
            else:
                self._parse_column_definition(table, clean_items)

        self.schema.tables[table_name] = table

    def _parse_column_definition(self, table: Table, tokens: List[sqlparse.sql.Token]):
        column_name = tokens[0].value.strip('"` ').lower()

        # The data type could be one word (INT, SERIAL, TIMESTAMP) or multiple words (DOUBLE PRECISION, CHARACTER VARYING)
        type_parts = []
        idx = 1

        constraint_keywords = ('NOT', 'NULL', 'PRIMARY', 'UNIQUE', 'DEFAULT', 'REFERENCES', 'CHECK', 'CONSTRAINT', 'NOT NULL', 'PRIMARY KEY')

        while idx < len(tokens):
            token = tokens[idx]
            val_upper = token.value.upper()
            if val_upper in constraint_keywords:
                break
            type_parts.append(token)
            idx += 1

        if not type_parts:
            raise DDLParserError(f"No data type specified for column '{column_name}' in table '{table.name}'")

        # First type part is usually the main type name
        type_str = type_parts[0].value.upper()
        max_length = None

        # Check if the next token is parenthesis (e.g. VARCHAR (50) or VARCHAR(50))
        if len(type_parts) > 1 and isinstance(type_parts[1], sqlparse.sql.Parenthesis):
            try:
                max_length = int(type_parts[1].value.strip('() \t\n'))
            except ValueError:
                pass

        # Map to ColumnType
        try:
            # Handle common aliases
            if type_str in ('INT', 'INTEGER'):
                data_type = ColumnType.INTEGER
            elif type_str == 'CHARACTER VARYING' or type_str == 'VARCHAR':
                data_type = ColumnType.VARCHAR
            elif type_str == 'CHARACTER' or type_str == 'CHAR':
                data_type = ColumnType.CHAR
            elif type_str == 'DOUBLE PRECISION':
                data_type = ColumnType.DOUBLE_PRECISION
            else:
                data_type = ColumnType[type_str]
        except KeyError:
            raise DDLParserError(f"Unknown data type '{type_str}' for column '{column_name}' in table '{table.name}'")

        column = Column(name=column_name, data_type=data_type, max_length=max_length)

        # Parse column-level constraints
        i = idx
        while i < len(tokens):
            tok = tokens[i]
            val_upper = tok.value.upper()

            if val_upper == 'NOT NULL':
                column.is_nullable = False
                i += 1
            elif val_upper == 'NOT' and i + 1 < len(tokens) and tokens[i+1].value.upper() == 'NULL':
                column.is_nullable = False
                i += 2
            elif val_upper == 'PRIMARY KEY':
                column.is_primary_key = True
                column.is_nullable = False
                table.primary_key.append(column_name)
                i += 1
            elif val_upper == 'PRIMARY' and i + 1 < len(tokens) and tokens[i+1].value.upper() == 'KEY':
                column.is_primary_key = True
                column.is_nullable = False
                table.primary_key.append(column_name)
                i += 2
            elif val_upper == 'UNIQUE':
                column.is_unique = True
                table.unique_constraints.append([column_name])
                i += 1
            elif val_upper == 'DEFAULT':
                if i + 1 < len(tokens):
                    column.default_value = tokens[i+1].value.strip("'\"")
                    i += 2
                else:
                    i += 1
            elif val_upper == 'REFERENCES':
                # REFERENCES parent_table (column)
                if i + 1 < len(tokens):
                    ref_table = tokens[i+1].value.strip('"` ').lower()
                    ref_col = None
                    i += 2
                    if i < len(tokens) and isinstance(tokens[i], sqlparse.sql.Parenthesis):
                        ref_col = tokens[i].value.strip('() \t\n"` ').lower()
                        i += 1

                    # Parse ON DELETE/ON UPDATE
                    on_delete = None
                    on_update = None
                    while i < len(tokens):
                        next_val = tokens[i].value.upper()
                        if next_val == 'ON' and i + 2 < len(tokens):
                            action_type = tokens[i+1].value.upper() # DELETE or UPDATE
                            action = tokens[i+2].value.upper()
                            if i + 3 < len(tokens) and tokens[i+3].value.upper() in ('NULL', 'ACTION'):
                                action += " " + tokens[i+3].value.upper()
                                i += 4
                            else:
                                i += 3

                            if action_type == 'DELETE':
                                on_delete = action
                            elif action_type == 'UPDATE':
                                on_update = action
                        else:
                            break

                    table.foreign_keys.append(ForeignKey(
                        column_name=column_name,
                        referenced_table=ref_table,
                        referenced_column=ref_col,
                        on_delete=on_delete,
                        on_update=on_update
                    ))
                else:
                    i += 1
            elif val_upper == 'CHECK':
                if i + 1 < len(tokens) and isinstance(tokens[i+1], sqlparse.sql.Parenthesis):
                    check_expr = tokens[i+1].value
                    column.check_constraint = check_expr
                    table.check_constraints.append(check_expr)
                    i += 2
                else:
                    i += 1
            else:
                i += 1

        table.columns.append(column)

    def _parse_table_level_constraint(self, table: Table, tokens: List[sqlparse.sql.Token]):
        idx = 0
        constraint_name = None
        if tokens[idx].value.upper() == 'CONSTRAINT':
            if idx + 1 < len(tokens):
                constraint_name = tokens[idx+1].value
                idx += 2
            else:
                idx += 1

        if idx >= len(tokens):
            return

        constraint_type = tokens[idx].value.upper()
        if constraint_type == 'PRIMARY KEY':
            if idx + 1 < len(tokens) and isinstance(tokens[idx+1], sqlparse.sql.Parenthesis):
                cols = [c.value.strip('"` ').lower() for c in tokens[idx+1].tokens if not c.is_whitespace and c.value not in ('(', ')', ',')]
                table.primary_key.extend(cols)
                # Set pk flag in columns
                for col in table.columns:
                    if col.name in cols:
                        col.is_primary_key = True
                        col.is_nullable = False
        elif constraint_type == 'PRIMARY' and idx + 1 < len(tokens) and tokens[idx+1].value.upper() == 'KEY':
            # PRIMARY KEY (col1, col2)
            if idx + 2 < len(tokens) and isinstance(tokens[idx+2], sqlparse.sql.Parenthesis):
                cols = [c.value.strip('"` ').lower() for c in tokens[idx+2].tokens if not c.is_whitespace and c.value not in ('(', ')', ',')]
                table.primary_key.extend(cols)
                # Set pk flag in columns
                for col in table.columns:
                    if col.name in cols:
                        col.is_primary_key = True
                        col.is_nullable = False
        elif constraint_type == 'FOREIGN KEY':
            if idx + 1 < len(tokens) and isinstance(tokens[idx+1], sqlparse.sql.Parenthesis):
                cols = [c.value.strip('"` ').lower() for c in tokens[idx+1].tokens if not c.is_whitespace and c.value not in ('(', ')', ',')]
                # Search for REFERENCES
                ref_idx = idx + 2
                while ref_idx < len(tokens):
                    if tokens[ref_idx].value.upper() == 'REFERENCES':
                        break
                    ref_idx += 1

                if ref_idx < len(tokens) and ref_idx + 1 < len(tokens):
                    ref_target = tokens[ref_idx+1]
                    ref_table = ""
                    ref_cols = []

                    if isinstance(ref_target, sqlparse.sql.Parenthesis):
                        pass
                    else:
                        ref_table = ref_target.value

                    if ref_idx + 2 < len(tokens) and isinstance(tokens[ref_idx+2], sqlparse.sql.Parenthesis):
                        ref_cols = [c.value.strip('"` ').lower() for c in tokens[ref_idx+2].tokens if not c.is_whitespace and c.value not in ('(', ')', ',')]

                    for k, col in enumerate(cols):
                        ref_col = ref_cols[k] if k < len(ref_cols) else None
                        table.foreign_keys.append(ForeignKey(
                            column_name=col,
                            referenced_table=ref_table.lower(),
                            referenced_column=ref_col
                        ))
        elif constraint_type == 'FOREIGN' and idx + 1 < len(tokens) and tokens[idx+1].value.upper() == 'KEY':
            # FOREIGN KEY (col) REFERENCES parent(ref_col)
            if idx + 2 < len(tokens) and isinstance(tokens[idx+2], sqlparse.sql.Parenthesis):
                cols = [c.value.strip('"` ').lower() for c in tokens[idx+2].tokens if not c.is_whitespace and c.value not in ('(', ')', ',')]
                # Search for REFERENCES
                ref_idx = idx + 3
                while ref_idx < len(tokens):
                    if tokens[ref_idx].value.upper() == 'REFERENCES':
                        break
                    ref_idx += 1

                if ref_idx < len(tokens) and ref_idx + 1 < len(tokens):
                    ref_target = tokens[ref_idx+1]
                    ref_table = ""
                    ref_cols = []

                    if isinstance(ref_target, sqlparse.sql.Parenthesis):
                        pass
                    else:
                        ref_table = ref_target.value

                    if ref_idx + 2 < len(tokens) and isinstance(tokens[ref_idx+2], sqlparse.sql.Parenthesis):
                        ref_cols = [c.value.strip('"` ').lower() for c in tokens[ref_idx+2].tokens if not c.is_whitespace and c.value not in ('(', ')', ',')]

                    for k, col in enumerate(cols):
                        ref_col = ref_cols[k] if k < len(ref_cols) else None
                        table.foreign_keys.append(ForeignKey(
                            column_name=col,
                            referenced_table=ref_table.lower(),
                            referenced_column=ref_col
                        ))
        elif constraint_type == 'UNIQUE':
            # UNIQUE (col1, col2)
            if idx + 1 < len(tokens) and isinstance(tokens[idx+1], sqlparse.sql.Parenthesis):
                cols = [c.value.strip('"` ').lower() for c in tokens[idx+1].tokens if not c.is_whitespace and c.value not in ('(', ')', ',')]
                table.unique_constraints.append(cols)
                # If single column, mark is_unique
                if len(cols) == 1:
                    for col in table.columns:
                        if col.name == cols[0]:
                            col.is_unique = True
        elif constraint_type == 'CHECK':
            # CHECK (expr)
            if idx + 1 < len(tokens) and isinstance(tokens[idx+1], sqlparse.sql.Parenthesis):
                table.check_constraints.append(tokens[idx+1].value)

    def _build_and_sort_dag(self):
        graph = nx.DiGraph()

        # Add all tables as nodes
        for table_name in self.schema.tables:
            graph.add_node(table_name)

        # Add edges based on foreign keys
        for table_name, table in self.schema.tables.items():
            for fk in table.foreign_keys:
                if fk.referenced_table not in self.schema.tables:
                    raise DDLParserError(f"Foreign key in table '{table_name}' references unknown table '{fk.referenced_table}'")
                graph.add_edge(fk.referenced_table, table_name) # Edge from parent to child

        try:
            self.schema.topological_order = list(nx.topological_sort(graph))
        except nx.NetworkXUnfeasible:
            raise DDLParserError("Circular foreign key dependency detected. Cannot determine a topological order.")
