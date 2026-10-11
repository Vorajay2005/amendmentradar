"""TrialRadar HTTP API (FastAPI). Thin layer over src/service.py; also serves the built React app."""
import sys
from pathlib import Path
from typing import Literal, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

import service

DIST = ROOT / "web" / "dist"
app = FastAPI(title="TrialRadar API", version="1.0",
              description="Risk estimates that assist trial designers. Not an approval tool.")


class Design(BaseModel):
    phase: Literal["PHASE2", "PHASE2/PHASE3", "PHASE3"] = "PHASE3"
    sponsor_class: Literal["INDUSTRY", "OTHER", "NIH", "FED", "OTHER_GOV", "NETWORK", "INDIV"] = "INDUSTRY"
    conditions: str = Field("", max_length=500)
    intervention_names: str = Field("", max_length=500)
    intervention_types: list[Literal["DRUG", "BIOLOGICAL", "DEVICE", "PROCEDURE", "BEHAVIORAL", "OTHER"]] = ["DRUG"]
    allocation: Literal["RANDOMIZED", "NON_RANDOMIZED", "NA"] = "RANDOMIZED"
    intervention_model: Literal["PARALLEL", "CROSSOVER", "SINGLE_GROUP", "FACTORIAL", "SEQUENTIAL"] = "PARALLEL"
    masking: Literal["NONE", "SINGLE", "DOUBLE", "TRIPLE", "QUADRUPLE"] = "NONE"
    n_arms: int = Field(2, ge=1, le=20)
    n_interventions: int = Field(2, ge=1, le=20)
    n_primary: int = Field(1, ge=1, le=20)
    n_secondary: int = Field(0, ge=0, le=50)
    eligibility: str = Field("", max_length=20000)
    min_age: int = Field(18, ge=0, le=120)
    max_age: Optional[int] = Field(None, ge=0, le=120)
    sex: Literal["ALL", "FEMALE", "MALE"] = "ALL"
    healthy_volunteers: bool = False
    has_dmc: bool = False
    fda_drug: bool = False
    start_year: int = Field(2026, ge=2000, le=2040)

    @model_validator(mode="after")
    def _need_condition(self):
        if not self.conditions.strip():
            raise ValueError("Please list at least one condition.")
        return self


class AnalyzeRequest(BaseModel):
    nct_id: Optional[str] = Field(None, max_length=20)
    design: Optional[Design] = None

    @model_validator(mode="after")
    def _one_of(self):
        if bool(self.nct_id) == bool(self.design):
            raise ValueError("Send either nct_id or design, not both.")
        return self


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    try:
        return service.analyze(nct_id=req.nct_id, design=req.design.model_dump() if req.design else None)
    except service.AnalyzeError as e:
        return JSONResponse(status_code=e.status, content={"error": {"code": e.code, "message": e.message}})


@app.get("/api/dashboard")
def dashboard():
    return service.dashboard()


@app.get("/api/reliability")
def reliability():
    return service.reliability()


@app.get("/api/examples")
def examples():
    return [
        {"nct_id": "NCT03827850", "kind": "hit", "title": "FGFR inhibitor in FGFR-dysregulated cancer",
         "blurb": "Retrospective hit: terminated for enrolment difficulties; the model placed it in the upper third.",
         "tag": "Illustrative, chosen by a fixed rule"},
        {"nct_id": "NCT03598036", "kind": "miss", "title": "Voclosporin dose exploration",
         "blurb": "Retrospective miss: terminated for low recruitment; the model placed it in the lower third.",
         "tag": "Illustrative, chosen by a fixed rule"},
        {"nct_id": "NCT06964230", "kind": "new", "title": "T3D-959 in Alzheimer's disease (Phase 2b/3)",
         "blurb": "Not yet recruiting when stored: no outcome exists yet, so this is a live-style estimate.",
         "tag": "Not yet recruiting"},
    ]


# ---- static React app (committed build in web/dist) ----
if (DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    f = (DIST / path).resolve()
    if path and DIST in f.parents and f.is_file():
        return FileResponse(f)
    index = DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"message": "The web build is missing. Run `make web` (needs Node) or `git checkout web/dist`."}, status_code=503)
