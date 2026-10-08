from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import uvicorn
import json

from relational_synth.parser.ddl_parser import DDLParser, DDLParserError
from relational_synth.engine.data_generator import DataGenerator
from relational_synth.fuzzer.fuzzer import Fuzzer

app = FastAPI(title="RelationalSynth API")

# Setup directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")

# Globals for current state
current_schema = None
current_generator = None

# API Models
class GenerateRequest(BaseModel):
    count: int = 100
    format: str = "sql" # sql, json, csv

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open(os.path.join(static_dir, "index.html"), "r") as f:
        return f.read()

@app.post("/api/parse")
async def parse_ddl(ddl: Dict[str, str]):
    global current_schema, current_generator
    try:
        content = ddl.get("content", "")
        parser = DDLParser()
        current_schema = parser.parse_ddl(content)
        current_generator = DataGenerator(current_schema)

        # Return serialized schema for the UI
        # We need to make it JSON serializable
        tables_info = []
        for name in current_schema.topological_order:
            table = current_schema.tables[name]
            tables_info.append({
                "name": table.name,
                "columns": [{"name": c.name, "type": c.data_type.value, "pk": c.is_primary_key, "fk": any(fk.column_name == c.name for fk in table.foreign_keys)} for c in table.columns],
                "foreign_keys": [{"column": fk.column_name, "ref_table": fk.referenced_table, "ref_col": fk.referenced_column} for fk in table.foreign_keys]
            })

        return {"status": "success", "tables": tables_info}
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

@app.post("/api/generate")
async def generate_data(req: GenerateRequest):
    global current_schema, current_generator
    if not current_schema:
        raise HTTPException(status_code=400, detail="No schema loaded")

    try:
        fuzzer = Fuzzer(current_schema, current_generator)
        data = fuzzer.generate_positive_seed(rows_per_table=req.count)

        if req.format == "sql":
            content = fuzzer.to_sql(data)
            return {"status": "success", "format": "sql", "content": content}
        elif req.format == "json":
            return {"status": "success", "format": "json", "content": data}

        return {"status": "success", "data": data}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

def run_server(schema_content: Optional[str] = None, port: int = 8080):
    global current_schema, current_generator
    if schema_content:
        parser = DDLParser()
        current_schema = parser.parse_ddl(schema_content)
        current_generator = DataGenerator(current_schema)

    uvicorn.run(app, host="127.0.0.1", port=port)
