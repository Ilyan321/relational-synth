import pytest
from relational_synth.parser.ddl_parser import DDLParser, DDLParserError
from relational_synth.parser.schema_model import ColumnType

@pytest.fixture
def simple_schema_ddl():
    return """
    CREATE TABLE departments (
        department_id SERIAL PRIMARY KEY,
        department_name VARCHAR(100) NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE students (
        student_id SERIAL PRIMARY KEY,
        first_name VARCHAR(50) NOT NULL,
        last_name VARCHAR(50) NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        department_id INT REFERENCES departments(department_id) ON DELETE SET NULL,
        enrollment_date DATE DEFAULT CURRENT_DATE
    );
    """

@pytest.fixture
def circular_schema_ddl():
    return """
    CREATE TABLE A (
        a_id SERIAL PRIMARY KEY,
        b_id INT REFERENCES B(b_id)
    );

    CREATE TABLE B (
        b_id SERIAL PRIMARY KEY,
        a_id INT REFERENCES A(a_id)
    );
    """

def test_parse_simple_schema(simple_schema_ddl):
    parser = DDLParser()
    schema = parser.parse_ddl(simple_schema_ddl)

    assert "departments" in schema.tables
    assert "students" in schema.tables

    dept_table = schema.tables["departments"]
    assert dept_table.name == "departments"
    assert len(dept_table.columns) == 3
    assert dept_table.primary_key == ["department_id"]
    assert len(dept_table.foreign_keys) == 0

    dept_id_col = next(c for c in dept_table.columns if c.name == "department_id")
    assert dept_id_col.data_type == ColumnType.SERIAL
    assert not dept_id_col.is_nullable
    assert dept_id_col.is_primary_key

    dept_name_col = next(c for c in dept_table.columns if c.name == "department_name")
    assert dept_name_col.data_type == ColumnType.VARCHAR
    assert not dept_name_col.is_nullable
    assert dept_name_col.is_unique
    assert dept_name_col.max_length == 100

    students_table = schema.tables["students"]
    assert students_table.name == "students"
    assert len(students_table.columns) == 6
    assert students_table.primary_key == ["student_id"]
    assert len(students_table.foreign_keys) == 1

    dept_id_fk = students_table.foreign_keys[0]
    assert dept_id_fk.column_name == "department_id"
    assert dept_id_fk.referenced_table == "departments"
    assert dept_id_fk.referenced_column == "department_id"
    assert dept_id_fk.on_delete == "SET NULL"

    assert schema.topological_order == ["departments", "students"]

def test_circular_dependency_detection(circular_schema_ddl):
    parser = DDLParser()
    with pytest.raises(DDLParserError, match="Circular foreign key dependency detected"):
        parser.parse_ddl(circular_schema_ddl)

def test_unknown_data_type():
    ddl = "CREATE TABLE test (id INT PRIMARY KEY, unknown_col UNKNOWN_TYPE);"
    parser = DDLParser()
    with pytest.raises(DDLParserError, match="Unknown data type 'UNKNOWN_TYPE'"):
        parser.parse_ddl(ddl)
