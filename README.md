# RelationalSynth (relsyn)

A high-performance Relational Schema Parser, Mock Data Synthesizer, and Database Integrity Testbench designed for PostgreSQL/Supabase DBMS workflows.

## Overview

RelationalSynth automatically parses SQL DDL files, resolves table Foreign-Key dependency graphs (DAGs), generates thousands of realistic interconnected mock records, fuzz-tests constraints, and provides both a CLI and an embedded browser visualizer.

## Features

- **DDL & Schema Parser**: Parses PostgreSQL DDL (`CREATE TABLE`), extracts relationships, and performs topological sorting using `networkx`.
- **Intelligent Synthetic Data Engine**: Generates semantic mock data using `Faker`, respecting `UNIQUE`, `CHECK`, `NOT NULL`, and `FOREIGN KEY` referential integrity.
- **Integrity Fuzzing**: Generates both compliant seed data and deliberate violation records (boundary testing) for stress-testing database triggers and constraints.
- **Embedded Web Visualizer**: FastAPI-powered UI with an interactive ER diagram (SVG) and one-click data generation.
- **Fast Performance**: Capable of generating 20,000+ interconnected rows in under 2 seconds.

## Installation

```bash
# Install the tool in editable mode
pip install -e ./relational-synth
```

## CLI Usage

### 1. Parse Schema
Prints a summary of the tables, columns, and the topological insertion order.
```bash
relsyn parse examples/schema.sql
```

### 2. Generate Seed Data
Generates 100% compliant SQL `INSERT` statements.
```bash
relsyn generate examples/schema.sql --count 5000 --output seed.sql
```

### 3. Fuzz Constraints
Generates negative boundary test vectors (deliberate violations) to verify database defenses.
```bash
relsyn fuzz examples/schema.sql --output fuzz_tests.sql
```

### 4. Launch Visualizer
Launches the web UI on port 8080.
```bash
relsyn serve examples/schema.sql --port 8080 --open
```

## Architecture

```mermaid
graph TD
    A[SQL DDL File] --> B{relsyn CLI};
    B -- parse --> C[DDL & Schema Parser];
    C -- Schema Model (DAG) --> D[Intelligent Synthetic Data Engine];
    D -- Valid Data --> E[Integrity Fuzzing & Stress-Testing Suite];
    E -- Positive / Negative Data --> F[SQL INSERT / CSV / JSON Output];

    B -- generate --> D;
    B -- fuzz --> E;
    B -- serve --> G[Embedded Web Visualizer (FastAPI)];

    G -- Schema API --> C;
    G -- Data Generation API --> D;
    G -- UI (HTML/JS/Tailwind) --> H[Interactive ER Graph & Column Editor];
```

## Testing

Run the test suite with `pytest`:
```bash
python3 -m pytest relational-synth/tests
```

## Implementation Details

- **Parser**: Uses `sqlparse` to tokenize DDL and a custom flattening logic to handle complex PostgreSQL syntax like `IF NOT EXISTS` and multi-word types.
- **DAG**: Table dependencies are modeled as a Directed Acyclic Graph. The tool detects and errors on circular dependencies to ensure a valid insertion order.
- **Semantic Mapping**: Automatically maps column names like `email`, `first_name`, `created_at` to appropriate `Faker` providers.
- **Constraint Enforcement**: Uses a retry-loop with backtracking to satisfy `UNIQUE` and `CHECK` constraints while maintaining referential integrity.
