"""Check PC chrome in the Editor while the standalone player owns the clock.

These are read-only layout checks, not native Windows display-mode tests.
"""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import unity_pc_ui_validation as review

OUT=ROOT/"results/unity_validation/standalone_20261005/layout"


def main():
    review.OUTPUT=OUT
    results={}
    for width,height in [(1366,768),(1920,1080),(2560,1440),(1280,800),(1920,800)]:
        for view in ["overview","settings","drawer","preview"]:
            name=f"window_{width}x{height}_{view}"
            actions=review.baseline()
            if view=="settings":actions.append(review.action("TogglePcMenu","settings"))
            if view=="drawer":actions.append(review.action("SelectStation","F012"))
            if view=="preview":actions.append(review.action("SetFirstPersonWindowVisible",True))
            case={"request":{"name":name,"width":width,"height":height,"seek_minute":-1,
                "layout_only":True,"settle_frames":24,"settle_seconds":1.2,"capture":True,"actions":actions},
                "expected":{"width":width,"height":height,"stations":79,"role":"PCController",
                    "authority":False,"synchronized":True,"preview":view=="preview",
                    "drawer":0 if view=="drawer" else None,"menu":"settings" if view=="settings" else None}}
            print("Recording "+name,flush=True)
            results[name]=review.record(name,case,40)
            warnings=results[name]["warnings"]
            results[name]["passed"] &= not warnings["chrome_outside_screen"] and not warnings["pc_text_overflow"]
            if view=="settings":
                report=json.loads((OUT/(name+".json")).read_text(encoding="utf-8-sig"))
                results[name]["display_mode_buttons_present"]={"Windowed","Fullscreen"}.issubset({b["name"] for b in report["buttons"]})
                results[name]["passed"] &= results[name]["display_mode_buttons_present"]
            print(json.dumps({"case":name,**results[name]},ensure_ascii=False),flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps({"scope":"Editor read-only layout; standalone owns playback",
        "cases":results,"passed":sum(r["passed"] for r in results.values()),
        "failed":sum(not r["passed"] for r in results.values())},ensure_ascii=False,indent=2),encoding="utf-8")
    if not all(r["passed"] for r in results.values()):raise SystemExit(1)


if __name__=="__main__":main()
