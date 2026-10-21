import pytest

from app.models.enums import OpType, get_op_type_info
from app.models.process_model import ProcessNode, ProcessDefinition
from app.utils.csv_parser import parse_process_csv, export_process_csv
from app.utils.validators import validate_csv_row


@pytest.mark.parametrize("code", ["S-Move", "S-Rest", "Coop"])
def test_new_behavior_survives_model_json_and_csv(code):
    node = ProcessNode(step_id="B001", task_name="基础行为", op_type=code, std_duration=5)
    process = ProcessDefinition(nodes=[node])
    restored = ProcessDefinition.model_validate_json(process.model_dump_json())
    assert restored.nodes[0].op_type.value == code
    parsed = parse_process_csv(export_process_csv(process))
    assert parsed.success
    assert parsed.warnings == []
    assert parsed.process.nodes[0].op_type.value == code
    assert get_op_type_info(node.op_type)["zh"] != "未知"


@pytest.mark.parametrize("code", ["S-MOVE", "s-rest", "COOP"])
def test_csv_accepts_case_variations_without_falling_back_to_assembly(code):
    csv = f"step_id,task_name,op_type,std_duration\nB001,行为,{code},5\n"
    parsed = parse_process_csv(csv)
    assert parsed.success
    assert parsed.warnings == []
    assert parsed.process.nodes[0].op_type != OpType.A
    row = {"step_id": "B001", "task_name": "行为", "op_type": code, "std_duration": "5"}
    valid, errors, warnings = validate_csv_row(row, 2, set())
    assert valid
    assert errors == []
    assert warnings == []


def test_new_behaviors_run_as_explicit_process_steps():
    from app.core.simulation_engine import SimulationEngine
    from app.models.config_model import GlobalConfig
    from app.models.enums import SimulationStatus

    codes = ["S-Move", "S-Rest", "Coop"]
    process = ProcessDefinition(nodes=[
        ProcessNode(step_id=f"B{i}", task_name=code, op_type=code,
                    predecessors=f"B{i-1}" if i else "", std_duration=5)
        for i, code in enumerate(codes)
    ])
    result = SimulationEngine(GlobalConfig(num_workers=2, target_output=1,
                                          work_days_per_month=1, pipeline_mode=False), process).run()
    assert result.status == SimulationStatus.COMPLETED
    assert result.engines_completed >= 1
    assert set(codes).issubset({event.op_type for event in result.gantt_events})


@pytest.mark.parametrize("code", ["S-Move", "S-Rest", "Coop"])
def test_process_and_simulation_api_models_accept_new_behaviors(code):
    from app.api.process import ProcessNode as ApiNode
    from app.api.simulation import SimulationRequest

    payload = {"step_id": "B001", "task_name": code, "op_type": code, "std_duration": 5}
    assert ApiNode.model_validate(payload).op_type.value == code
    request = SimulationRequest.model_validate({"config": {}, "process": {"nodes": [payload]}, "publish_to_clients": False})
    assert request.process.nodes[0].op_type.value == code
