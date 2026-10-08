from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Any

class ColumnType(Enum):
    # Basic types
    TEXT = "TEXT"
    VARCHAR = "VARCHAR"
    CHAR = "CHAR"
    INT = "INT"
    INTEGER = "INTEGER"
    SMALLINT = "SMALLINT"
    BIGINT = "BIGINT"
    NUMERIC = "NUMERIC"
    DECIMAL = "DECIMAL"
    REAL = "REAL"
    DOUBLE_PRECISION = "DOUBLE PRECISION"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    TIME = "TIME"
    TIMESTAMP = "TIMESTAMP"
    UUID = "UUID"
    JSON = "JSON"
    JSONB = "JSONB"
    BYTEA = "BYTEA" # Binary data

    # PostgreSQL specific types
    SERIAL = "SERIAL"
    BIGSERIAL = "BIGSERIAL"
    SMALLSERIAL = "SMALLSERIAL"
    # Add more as needed

@dataclass
class Column:
    name: str
    data_type: ColumnType
    is_nullable: bool = True
    is_primary_key: bool = False
    is_unique: bool = False
    default_value: Optional[str] = None
    check_constraint: Optional[str] = None
    max_length: Optional[int] = None # For VARCHAR, CHAR

@dataclass
class ForeignKey:
    column_name: str
    referenced_table: str
    referenced_column: str
    on_delete: Optional[str] = None # e.g., "SET NULL", "CASCADE", "RESTRICT", "NO ACTION"
    on_update: Optional[str] = None

@dataclass
class Table:
    name: str
    columns: List[Column] = field(default_factory=list)
    primary_key: List[str] = field(default_factory=list)
    foreign_keys: List[ForeignKey] = field(default_factory=list)
    unique_constraints: List[List[str]] = field(default_factory=list) # List of column lists for composite unique
    check_constraints: List[str] = field(default_factory=list) # List of CHECK expressions
    enums: Dict[str, List[str]] = field(default_factory=dict) # For ENUM types defined within the table scope

@dataclass
class Schema:
    tables: Dict[str, Table] = field(default_factory=dict)
    # The topological order of table names for insertion
    # This will be derived from the DAG
    topological_order: List[str] = field(default_factory=list)
    # Raw DDL statements (optional, for debugging or full schema reconstruction)
    raw_ddl: Optional[str] = None
