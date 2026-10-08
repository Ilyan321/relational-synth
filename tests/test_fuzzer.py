import pytest
from relational_synth.parser.ddl_parser import DDLParser
from relational_synth.engine.data_generator import DataGenerator
from relational_synth.fuzzer.fuzzer import Fuzzer

@pytest.fixture
def fuzzer_schema():
    ddl = """
    CREATE TABLE groups (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE members (
        id SERIAL PRIMARY KEY,
        group_id INT NOT NULL REFERENCES groups(id),
        email TEXT NOT NULL UNIQUE,
        age INT CHECK (age >= 18)
    );
    """
    parser = DDLParser()
    return parser.parse_ddl(ddl)

def test_fuzzer_positive_sql(fuzzer_schema):
    generator = DataGenerator(fuzzer_schema, seed=1)
    fuzzer = Fuzzer(fuzzer_schema, generator)

    data = fuzzer.generate_positive_seed(rows_per_table=5)
    sql = fuzzer.to_sql(data)

    assert "INSERT INTO groups" in sql
    assert "INSERT INTO members" in sql
    assert sql.count("INSERT INTO groups") == 5
    assert sql.count("INSERT INTO members") == 5

    # Check topological order: groups should be before members
    groups_idx = sql.find("INSERT INTO groups")
    members_idx = sql.find("INSERT INTO members")
    assert groups_idx < members_idx

def test_fuzzer_negative_cases(fuzzer_schema):
    generator = DataGenerator(fuzzer_schema, seed=1)
    # Must generate some positive data first for duplicate unique checks to work
    generator.generate_all(rows_per_table=5)

    fuzzer = Fuzzer(fuzzer_schema, generator)
    fuzz_sql = fuzzer.generate_negative_fuzz()

    # 1. NOT NULL violations
    assert "Violation: NULL in NOT NULL column 'name'" in fuzz_sql
    assert "Violation: NULL in NOT NULL column 'group_id'" in fuzz_sql

    # 2. CHECK violations
    assert "Violation: CHECK constraint violation on 'age'" in fuzz_sql

    # 3. UNIQUE violations
    assert "Violation: Duplicate value in UNIQUE column 'name'" in fuzz_sql

    # 4. FK violations
    assert "Violation: Orphan Foreign Key reference on 'group_id'" in fuzz_sql
    assert "99999999" in fuzz_sql # Our non-existent ID
