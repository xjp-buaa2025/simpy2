"""Record real PC area UI against the web-published run; no fabricated events."""
import json
from pathlib import Path
from tools import unity_pc_ui_validation as review

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/area_capacity_validation'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    review.OUTPUT = OUT
    replay = json.loads((ROOT/'results/unity_validation/replay.json').read_text(encoding='utf-8'))
    result = json.loads((ROOT/'results/unity_validation/current_result.json').read_text(encoding='utf-8'))['data']
    checks = dict(stations=len(replay['stations'])==79,
        same_run=replay['sim_id']==result['sim_id'],
        area_stats=replay['area_stats']==result['area_stats'],
        completions=replay['area_completion_events']==result['area_completion_events'],
        resources=replay['resource_snapshot']==result['resource_snapshot'],
        evaluation=replay['evaluation_context']==result['evaluation_context'],
        unfinished=any(e['event_type']=='IN_PROGRESS' for e in replay['events']))
    assert all(checks.values()), checks
    reports = []
    for width,height,minute,suffix in [(1366,768,3000,'mid_1366'),(1920,1080,replay['duration'],'end_1920')]:
        name='area_capacity_pc_'+suffix
        case=dict(request=dict(name=name,sim_id=replay['sim_id'],width=width,height=height,
            seek_minute=minute,speed=20,settle_frames=15,settle_seconds=1,capture=True,
            actions=[review.action('SetFirstPersonWindowVisible',False),review.action('SelectStation','Q001'),review.action('OpenPcDrawer',4)]),
            expected=dict(width=width,height=height,stations=79,role='PCController',authority=True,
                synchronized=True,preview=False,drawer=4,exact_minute=minute))
        report=review.record(name,case,90)
        assert report['passed'],report
        raw=json.loads((OUT/(name+'.json')).read_text(encoding='utf-8-sig'))
        texts=[t['text'] for t in raw['texts'] if 'AreaDetails' in t['path']]
        assert texts and '当前回放完成' in texts[0] and '评估期末完成' in texts[0],texts
        if minute==replay['duration']:
            count=next(s['completed_units'] for s in replay['area_stats'] if s['area_id']=='ST13')
            assert f'当前回放完成：{count} 套' in texts[0],texts[0]
        reports.append(report)
    summary=dict(passed=True,run_id=replay['sim_id'],checks=checks,pc=reports,headset_tested=False)
    (OUT/'integration.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=True,checks=checks,pc_captures=len(reports)),ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
