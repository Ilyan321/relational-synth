import re
from typing import Any, Callable, Dict, List, Optional
from faker import Faker
from relational_synth.parser.schema_model import ColumnType, Column

class SemanticRules:
    def __init__(self, faker: Faker):
        self.faker = faker

        # Mapping patterns (regex) of column names to Faker generator functions
        self.column_name_patterns: List[tuple[re.Pattern, Callable[[], Any]]] = [
            (re.compile(r'email', re.IGNORECASE), self.faker.unique.email),
            (re.compile(r'first_name|firstname', re.IGNORECASE), self.faker.first_name),
            (re.compile(r'last_name|lastname', re.IGNORECASE), self.faker.last_name),
            (re.compile(r'username|user_name|login', re.IGNORECASE), self.faker.unique.user_name),
            (re.compile(r'phone|telephone|mobile|cell', re.IGNORECASE), self.faker.phone_number),
            (re.compile(r'price|amount|balance|cost|salary', re.IGNORECASE), lambda: round(self.faker.pyfloat(left_digits=4, right_digits=2, min_value=1.0, max_value=9999.0), 2)),
            (re.compile(r'created_at|updated_at|createdat|updatedat', re.IGNORECASE), lambda: self.faker.date_time_between(start_date='-2y', end_date='now').isoformat()),
            (re.compile(r'birth_date|birthdate|dob', re.IGNORECASE), lambda: self.faker.date_of_birth(minimum_age=18, maximum_age=90).isoformat()),
            (re.compile(r'date', re.IGNORECASE), lambda: self.faker.date_between(start_date='-1y', end_date='now').isoformat()),
            (re.compile(r'ip_address|ipaddress|ip|ipv4', re.IGNORECASE), self.faker.ipv4),
            (re.compile(r'ipv6', re.IGNORECASE), self.faker.ipv6),
            (re.compile(r'uuid', re.IGNORECASE), self.faker.uuid4),
            (re.compile(r'postal_code|postalcode|zip|zipcode', re.IGNORECASE), self.faker.postcode),
            (re.compile(r'country', re.IGNORECASE), self.faker.country),
            (re.compile(r'city', re.IGNORECASE), self.faker.city),
            (re.compile(r'street|address', re.IGNORECASE), self.faker.street_address),
            (re.compile(r'state', re.IGNORECASE), self.faker.state),
            (re.compile(r'url|website|link', re.IGNORECASE), self.faker.url),
            (re.compile(r'company|employer|organization', re.IGNORECASE), self.faker.company),
            (re.compile(r'status|state|category|type', re.IGNORECASE), lambda: self.faker.random_element(elements=['active', 'inactive', 'pending', 'completed'])),
            (re.compile(r'description|summary|bio|notes|comment', re.IGNORECASE), self.faker.paragraph),
            (re.compile(r'title|name|subject', re.IGNORECASE), self.faker.catch_phrase),
            (re.compile(r'age', re.IGNORECASE), lambda: self.faker.random_int(min=18, max=80)),
        ]

    def get_generator_for_column(self, column: Column) -> Callable[[], Any]:
        # 1. Try to match by column name pattern
        for pattern, generator in self.column_name_patterns:
            if pattern.search(column.name):
                # If it's unique, wrap in unique if not already done
                if column.is_unique:
                    return lambda: self._wrap_unique(generator)
                return generator

        # 2. Fall back to column type defaults
        return self.get_generator_for_type(column.data_type, column.is_unique)

    def _wrap_unique(self, generator: Callable[[], Any], max_attempts: int = 1000) -> Any:
        # A simple unique wrapper if faker's own unique is not working or to protect custom lambdas
        # Normally faker.unique handles this, but custom lambda wrappers might need extra handling.
        # We handle this mainly in the core data generator engine to prevent state issues.
        return generator()

    def get_generator_for_type(self, data_type: ColumnType, is_unique: bool = False) -> Callable[[], Any]:
        f = self.faker

        # Setup specific type generators
        if data_type in (ColumnType.INT, ColumnType.INTEGER, ColumnType.SMALLINT, ColumnType.BIGINT):
            gen = lambda: f.random_int(min=1, max=1000000)
        elif data_type in (ColumnType.SERIAL, ColumnType.BIGSERIAL, ColumnType.SMALLSERIAL):
            # Serial types are auto-incrementing, we'll handle this in the generator state,
            # but as fallback return random int.
            gen = lambda: f.random_int(min=1, max=1000000)
        elif data_type in (ColumnType.VARCHAR, ColumnType.TEXT, ColumnType.CHAR):
            gen = f.word
        elif data_type in (ColumnType.NUMERIC, ColumnType.DECIMAL, ColumnType.REAL, ColumnType.DOUBLE_PRECISION):
            gen = lambda: round(f.pyfloat(left_digits=4, right_digits=2, min_value=0.0, max_value=10000.0), 2)
        elif data_type == ColumnType.BOOLEAN:
            gen = f.boolean
        elif data_type == ColumnType.DATE:
            gen = lambda: f.date_between(start_date='-5y', end_date='now').isoformat()
        elif data_type == ColumnType.TIME:
            gen = lambda: f.time()
        elif data_type == ColumnType.TIMESTAMP:
            gen = lambda: f.date_time_between(start_date='-5y', end_date='now').isoformat()
        elif data_type == ColumnType.UUID:
            gen = f.uuid4
        elif data_type in (ColumnType.JSON, ColumnType.JSONB):
            gen = lambda: f.json(data_columns={'id': 'pyint', 'name': 'name', 'active': 'pybool'}, num_rows=1)
        elif data_type == ColumnType.BYTEA:
            gen = lambda: f.binary(length=16)
        else:
            gen = f.word

        if is_unique:
            # Wrap in faker's unique if unique
            try:
                return getattr(f.unique, gen.__name__)
            except AttributeError:
                # Custom lambda/wrapper, return directly; uniqueness is enforced globally in engine/data_generator.py
                return gen
        return gen
