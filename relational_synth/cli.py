import typer
import sys
import os
from typing import Optional
from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel

from relational_synth.parser.ddl_parser import DDLParser, DDLParserError
from relational_synth.engine.data_generator import DataGenerator
from relational_synth.fuzzer.fuzzer import Fuzzer
from relational_synth.web.main import run_server

app = typer.Typer(name="relsyn", help="RelationalSynth: Relational Schema Parser, Mock Data Synthesizer, and Database Integrity Testbench")
console = Console()

@app.command()
def version():
    """
    Prints the version of RelationalSynth.
    """
    console.print("[bold green]RelationalSynth[/bold green] version [cyan]0.1.0[/cyan]")

@app.command()
def parse(
    schema_file: str = typer.Argument(..., help="Path to the SQL DDL schema file.")
):
    """
    Parses a SQL DDL schema file and prints a summary including topological order.
    """
    try:
        parser = DDLParser()
        schema = parser.parse_ddl_from_file(schema_file)

        console.print(Panel(f"[bold blue]Schema Summary for {schema_file}[/bold blue]", expand=False))

        table = RichTable(title="Tables & Columns")
        table.add_column("Order", style="dim")
        table.add_column("Table Name", style="bold cyan")
        table.add_column("Columns", style="green")
        table.add_column("FK Dependencies", style="yellow")

        for i, name in enumerate(schema.topological_order, 1):
            t = schema.tables[name]
            cols = ", ".join([c.name for c in t.columns])
            deps = ", ".join(set([fk.referenced_table for fk in t.foreign_keys]))
            table.add_row(str(i), name, cols, deps or "None")

        console.print(table)
        console.print(f"\n[bold green]Topological Insertion Order:[/bold green] {' -> '.join(schema.topological_order)}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)

@app.command()
def generate(
    schema_file: str = typer.Argument(..., help="Path to the SQL DDL schema file."),
    count: int = typer.Option(5000, "--count", "-c", help="Number of rows to generate per table."),
    output: str = typer.Option("seed.sql", "--output", "-o", help="Output file for the generated SQL INSERT statements."),
    seed: Optional[int] = typer.Option(None, "--seed", help="Random seed for deterministic generation."),
):
    """
    Generates mock data based on the schema and outputs SQL INSERT statements.
    """
    try:
        parser = DDLParser()
        schema = parser.parse_ddl_from_file(schema_file)

        generator = DataGenerator(schema, seed=seed)
        fuzzer = Fuzzer(schema, generator)

        console.print(f"Generating [bold cyan]{count}[/bold cyan] rows per table...")
        data = fuzzer.generate_positive_seed(rows_per_table=count)

        sql_content = fuzzer.to_sql(data)

        with open(output, "w") as f:
            f.write(sql_content)

        console.print(f"[bold green]Success![/bold green] Seed data written to [cyan]{output}[/cyan]")

    except Exception as e:
        console.print(f"[bold red]Error during generation:[/bold red] {str(e)}")
        sys.exit(1)

@app.command()
def fuzz(
    schema_file: str = typer.Argument(..., help="Path to the SQL DDL schema file."),
    output: str = typer.Option("fuzz_tests.sql", "--output", "-o", help="Output file for the generated negative boundary test vectors."),
    seed: Optional[int] = typer.Option(None, "--seed", help="Random seed for deterministic generation."),
):
    """
    Generates negative boundary test vectors for schema integrity fuzzing.
    """
    try:
        parser = DDLParser()
        schema = parser.parse_ddl_from_file(schema_file)

        generator = DataGenerator(schema, seed=seed)
        # Generate a few rows of good data first so duplicates can be tested
        generator.generate_all(rows_per_table=5)

        fuzzer = Fuzzer(schema, generator)

        console.print(f"Generating fuzz test vectors for [bold cyan]{schema_file}[/bold cyan]...")
        fuzz_sql = fuzzer.generate_negative_fuzz()

        with open(output, "w") as f:
            f.write(fuzz_sql)

        console.print(f"[bold green]Success![/bold green] Fuzz tests written to [cyan]{output}[/cyan]")

    except Exception as e:
        console.print(f"[bold red]Error during fuzzing:[/bold red] {str(e)}")
        sys.exit(1)

@app.command()
def serve(
    schema_file: str = typer.Argument(..., help="Path to the SQL DDL schema file."),
    port: int = typer.Option(8080, "--port", "-p", help="Port for the web visualizer."),
    open_browser: bool = typer.Option(False, "--open", help="Open the web visualizer in the default browser."),
):
    """
    Launches the embedded web visualizer for interactive schema exploration and data generation.
    """
    try:
        # Check if file exists
        if not os.path.exists(schema_file):
            console.print(f"[bold red]Error:[/bold red] File {schema_file} not found.")
            sys.exit(1)

        with open(schema_file, "r") as f:
            content = f.read()

        console.print(f"Starting [bold green]RelationalSynth[/bold green] visualizer on [bold cyan]http://127.0.0.1:{port}[/bold cyan]")

        if open_browser:
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{port}")

        run_server(schema_content=content, port=port)

    except Exception as e:
        console.print(f"[bold red]Error launching server:[/bold red] {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    app()
