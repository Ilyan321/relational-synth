import pytest
import time
from relational_synth.parser.ddl_parser import DDLParser
from relational_synth.engine.data_generator import DataGenerator, DataGeneratorError

@pytest.fixture
def simple_schema():
    ddl = """
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
    parser = DDLParser()
    return parser.parse_ddl(ddl)

def test_data_generation_correctness(simple_schema):
    generator = DataGenerator(simple_schema, seed=42)
    data = generator.generate_all(rows_per_table=50)

    assert "departments" in data
    assert "students" in data

    depts = data["departments"]
    students = data["students"]

    assert len(depts) == 50
    assert len(students) == 50

    # 1. Verify Auto-incrementing SERIAL primary keys
    dept_ids = [d["department_id"] for d in depts]
    assert dept_ids == list(range(1, 51))

    student_ids = [s["student_id"] for s in students]
    assert student_ids == list(range(1, 51))

    # 2. Verify UNIQUE constraint on department_name and email
    dept_names = [d["department_name"] for d in depts]
    assert len(set(dept_names)) == 50 # No duplicates

    emails = [s["email"] for s in students]
    assert len(set(emails)) == 50 # No duplicates

    # 3. Verify Foreign Key Referential Integrity
    for student in students:
        dept_id = student["department_id"]
        if dept_id is not None:
            assert dept_id in dept_ids

def test_performance_benchmark(simple_schema):
    generator = DataGenerator(simple_schema, seed=42)

    start_time = time.time()
    data = generator.generate_all(rows_per_table=1000) # 2000 total rows
    duration = time.time() - start_time

    # Check that we generated 1000 rows per table
    assert len(data["departments"]) == 1000
    assert len(data["students"]) == 1000

    # Must generate 2000 total rows very quickly (requirement says 1000-20000+ in under 2 seconds)
    print(f"Generated 2000 rows in {duration:.4f} seconds")
    assert duration < 1.0 # Should easily be under 1 second on any modern processor

def test_check_constraint_enforcement():
    # Schema with CHECK constraints
    ddl = """
    CREATE TABLE users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) NOT NULL UNIQUE,
        age INT CHECK (age >= 18),
        status VARCHAR(20) CHECK (status IN ('active', 'inactive'))
    );
    """
    parser = DDLParser()
    schema = parser.parse_ddl(ddl)
    generator = DataGenerator(schema, seed=123)
    data = generator.generate_all(rows_per_table=100)

    users = data["users"]
    assert len(users) == 100

    for u in users:
        # Enforce CHECK age >= 18 (if not null)
        if u["age"] is not None:
            assert u["age"] >= 18
        # Enforce CHECK status IN ('active', 'inactive') (if not null)
        if u["status"] is not None:
            assert u["status"] in ('active', 'inactive')
