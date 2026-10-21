import csv
import io
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.api.process import router
from app.models.process_model import ProcessDefinition
from app.utils.csv_parser import export_process_csv, parse_csv_file, parse_process_csv
from app.utils.process_file_parser import ProcessFileError, parse_process_file


HEADERS = ["step_id", "task_name", "op_type", "predecessors", "std_duration", "station"]


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api/process")
    return TestClient(app)


def workbook(headers, rows, *, sheets=None):
    book = Workbook()
    sheet = book.active
    sheet.title = "工艺输入"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    for name, values in (sheets or {}).items():
        extra = book.create_sheet(name)
        for row in values:
            extra.append(row)
    output = io.BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def upload(client, filename, content, endpoint="parse-file"):
    return client.post(f"/api/process/{endpoint}", files={"file": (filename, content)}).json()


@pytest.mark.parametrize("alias", ["WSation", "WStation", "station", "工位编号"])
def test_xlsx_station_aliases_keep_behavior_and_bind_unity_ids(client, alias):
    data = upload(client, "input.xlsx", workbook(HEADERS[:-1] + [alias], [
        ["P1", "装配", "A", "", 5, "WS-P08"],
        ["P2", "工间移动", "S-Move", "P1", 2, "WS-P08"],
        ["P3", "休息", "S-Rest", "P2", 1, "WS-P08"],
        ["P4", "沟通", "Coop", "P3", 1, "WS-P08"],
    ]))
    assert data["success"]
    process = data["data"]
    assert process["name"] == "input"
    assert [n["op_type"] for n in process["nodes"]] == ["A", "S-Move", "S-Rest", "Coop"]
    assert all(n["station"] == n["area_id"] == n["workstation_id"] == "WS-P08" for n in process["nodes"])
    assert process["station_catalog"][0]["station_id"] == "WS-P08"
    assert process["station_catalog"][0]["label"] != "WS-P08"


def test_catalog_uses_layout_order_and_appends_unknown_stations():
    layout = json.loads(Path("data/factory_layout/pt6a29/layout.json").read_text(encoding="utf-8-sig"))
    known = [row for row in layout["zones"] if row["kind"] == "workstation"]
    rows = [[f"p{i}", "工序", "A", "", 1, row["station_id"]] for i, row in enumerate(reversed(known))]
    rows.insert(0, ["new", "未知工位", "A", "", 1, "WS-CUSTOM"])
    process = parse_process_file("process.xlsx", workbook(HEADERS, rows))
    assert [row["station_id"] for row in process.station_catalog] == [row["station_id"] for row in known] + ["WS-CUSTOM"]
    assert [row["label"] for row in process.station_catalog[:-1]] == [row["label"] for row in known]
    assert process.station_catalog[-1] == {"station_id": "WS-CUSTOM", "area_id": "WS-CUSTOM", "label": "WS-CUSTOM"}


def test_csv_backward_defaults_and_explicit_binding_priority(client):
    minimal = b"step_id,task_name,op_type,std_duration\na,first,A,5\n"
    legacy = upload(client, "legacy.CSV", minimal, "parse-csv")
    assert legacy["success"]
    node = legacy["data"]["nodes"][0]
    assert (node["station"], node["area_id"], node["workstation_id"]) == ("ST01", "", "")
    content = "step_id,task_name,op_type,std_duration,station,area_id,workstation_id\na,first,A,5,ST03,AREA-X,WS-P08\n"
    explicit = upload(client, "process.csv", content.encode())["data"]["nodes"][0]
    assert (explicit["station"], explicit["area_id"], explicit["workstation_id"]) == ("ST03", "AREA-X", "WS-P08")
    assert parse_process_csv(minimal.decode()).success


def test_csv_api_and_utility_roundtrips_preserve_binding(client):
    source = parse_process_file("process.xlsx", workbook(HEADERS, [["a", "装配", "Coop", "", 5, "WS-P08"]]))
    restored = parse_csv_file(export_process_csv(source).encode("utf-8-sig"))
    assert restored.success
    assert restored.process.nodes[0].model_dump() == source.nodes[0].model_dump()
    exported = client.post("/api/process/export-csv", json=source.model_dump(mode="json"))
    assert exported.status_code == 200
    headers = next(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert headers[-2:] == ["area_id", "workstation_id"]
    imported = upload(client, "process.csv", exported.content)
    assert imported["success"]
    assert imported["data"]["nodes"] == source.model_dump(mode="json")["nodes"]
    assert ProcessDefinition.model_validate_json(source.model_dump_json()).station_catalog == source.station_catalog


@pytest.mark.parametrize(("rows", "field", "row"), [
    ([["p", "first", "A", "", 2, "WS-P08"], ["p", "second", "A", "", 2, "WS-P08"]], "step_id", 3),
    ([["p", "first", "A", "missing", 2, "WS-P08"]], "predecessors", 2),
    ([["p", "first", "A", "q", 2, "WS-P08"], ["q", "second", "A", "p", 2, "WS-P08"]], "predecessors", 2),
    ([["p", "first", "A", "", "wrong", "WS-P08"]], "std_duration", 2),
    ([["p", "first", "unknown", "", 2, "WS-P08"]], "op_type", 2),
    ([["p", "first", "A", "", "=1+1", "WS-P08"]], "std_duration", 2),
    ([["p", "first", "A", "", 2, None]], "station", 2),
    ([["p", "first", "A", "", None, "WS-P08"]], "std_duration", 2),
])
def test_failure_returns_sheet_row_and_field_without_partial_process(client, rows, field, row):
    result = upload(client, "broken.xlsx", workbook(HEADERS, rows))
    assert not result["success"]
    assert result["data"]["parsed_count"] == 0
    assert "nodes" not in result["data"]
    assert any(i["sheet"] == "工艺输入" and i["field"] == field and i["row"] == row for i in result["data"]["issues"])


def test_unique_process_sheet_ignores_readme_but_rejects_ambiguous_sheets(client):
    valid = workbook(HEADERS, [["p", "first", "A", "", 1, "WS-P08"]], sheets={"说明": [["说明文本"]]})
    assert upload(client, "valid.xlsx", valid)["success"]
    ambiguous = workbook(HEADERS, [["p", "first", "A", "", 1, "WS-P08"]], sheets={"第二份工艺": [HEADERS, ["q", "second", "A", "", 1, "WS-P08"]]})
    result = upload(client, "ambiguous.xlsx", ambiguous)
    assert not result["success"]
    assert result["data"]["issues"][0]["field"] == "sheet"


def test_blank_rows_and_csv_gbk_are_supported(client):
    content = "\nstep_id,task_name,op_type,std_duration,WSation\n\na,装配,A,5,WS-P08\n"
    result = upload(client, "gbk.csv", content.encode("gbk"))
    assert result["success"]
    assert result["data"]["nodes"][0]["task_name"] == "装配"
    assert result["data"]["nodes"][0]["workstation_id"] == "WS-P08"


def test_missing_headers_corrupt_files_and_fractional_workers_are_rejected(client):
    for filename, content in [("broken.xlsx", b"not an xlsx"), ("input.xls", b"old excel"), ("empty.csv", b"")]:
        assert not upload(client, filename, content)["success"]
    bad_headers = upload(client, "headers.xlsx", workbook(["step_id", "task_name"], [["p", "first"]]))
    assert not bad_headers["success"]
    assert {i["field"] for i in bad_headers["data"]["issues"]} == {"op_type", "std_duration"}
    with pytest.raises(ProcessFileError) as error:
        parse_process_file("fraction.csv", b"step_id,task_name,op_type,std_duration,required_workers\na,first,A,5,1.5\n")
    assert error.value.issues[0]["field"] == "required_workers"
