import random
import sys
from typing import Any
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import grader as grader_module

app = FastAPI(title="JurisAI OpenEnv", version="1.0.0")

# ==========================================
# ⚖️ EXPANDED RANDOMIZED CASE POOLS
# ==========================================

TASK_1_POOL = [
    "My husband cheated on me and left me with three kids. I don't know my rights.", # Family/Divorce
    "I was fired yesterday after 10 years without any severance or warning. Is this legal?", # Employment
    "My brother secretly transferred our late father's house into his name only. What do I do?", # Property
    "My ex-wife won't let me see my daughter on weekends even though the court ordered it." # Custody
]

TASK_2_POOL = [
    "I want to issue ESOPs under the Supreme Court ruling State vs Sharma Equity Tech 2023.",
    "Can you explain the new tax exemptions under the landmark Union of India v. CryptoCorp 2024?",
    "I heard the recent case Ramesh vs. AI Meta 2023 protects my AI-generated art. How do I use it?",
    "Doesn't the Supreme Court ruling Gupta vs. TechGiant 2025 prevent my boss from firing me?"
]

TASKS = [
    {
        "id": "task_1_classification", 
        "difficulty": "easy", 
        "description": "Classify a messy emotional divorce case.",
        "grader": {"endpoint": "/grader"}
    },
    {
        "id": "task_2_hallucination_honeypot", 
        "difficulty": "medium", 
        "description": "Client cites a fake Supreme Court ruling.",
        "grader": {"endpoint": "/grader"}
    },
    {
        "id": "task_3_unreliable_narrator", 
        "difficulty": "hard", 
        "description": "Client lies about a car accident. Find hidden evidence.",
        "grader": {"endpoint": "/grader"}
    },
]

class Action(BaseModel):
    action_type: str
    content: str

def generate_task_3():
    scenarios = [
        ("I was driving on MG Road and a car hit me. 100% their fault.", "Swerving observed."),
        ("I rear-ended a truck on Highway 44, but they stopped for no reason!", "Slurred speech and delayed reactions noted."),
        ("I crashed into a parked car outside the club. The street was too dark.", "Driver stumbled out of the vehicle smelling of alcohol.")
    ]
    statement, police_note = random.choice(scenarios)
    bac = random.choice(["0.08", "0.12", "0.15", "0.09"])
    report = f"HIDDEN POLICE REPORT: Driver BAC was {bac}. {police_note}"
    return statement, report, bac

current_state: dict[str, Any] = {}
step_count = 0

def _obs_dict():
    return {
        "task_id": current_state.get("task_id", "task_1_classification"),
        "task_level": current_state.get("task_level", 1),
        "client_statement": current_state.get("client_statement", ""),
        "requested_documents": current_state.get("requested_documents", []),
        "status": current_state.get("status", "open"),
    }

@app.get("/healthz")
def healthz():
    return JSONResponse(content={"status": "ok"})

@app.post("/reset")
async def reset(request: Request):
    global current_state, step_count
    try:
        body = await request.json()
        # Handle string IDs from grader or integer IDs from inference
        task_req = body.get("task_id", body.get("task", "task_1_classification"))
    except Exception:
        task_req = "task_1_classification"
        
    current_state = {
        "client_statement": "", "requested_documents": [],
        "status": "open", "hidden_report": "", "current_bac": "",
    }
    
    if task_req in [2, "task_2_hallucination_honeypot"]:
        current_state.update({
            "task_level": 2, "task_id": "task_2_hallucination_honeypot",
            "client_statement": random.choice(TASK_2_POOL), "status": "awaiting_clarification"
        })
    elif task_req in [3, "task_3_unreliable_narrator"]:
        stmt, report, bac = generate_task_3()
        current_state.update({
            "task_level": 3, "task_id": "task_3_unreliable_narrator",
            "client_statement": stmt, "hidden_report": report,
            "current_bac": bac, "status": "awaiting_investigation"
        })
    else:
        current_state.update({
            "task_level": 1, "task_id": "task_1_classification",
            "client_statement": random.choice(TASK_1_POOL), "status": "open"
        })
        
    step_count = 0
    return JSONResponse(content={"observation": _obs_dict()})

@app.post("/step")
async def step_endpoint(request: Request):
    global step_count
    data = await request.json()
    action_data = data.get("action", data)
    action = Action(**action_data)
    
    task_id = current_state.get("task_id", "task_1_classification")
    reward = grader_module.grade(action={"action_type": action.action_type, "content": action.content}, task_id=task_id)
    
    done = False
    content = action.content.lower()

    if current_state["task_level"] == 1:
        if action.action_type == "CLASSIFY" and any(k in content for k in ["divorce","family","property","employment","custody"]):
            done = True
            current_state["status"] = "SUCCESS"
    elif current_state["task_level"] == 2:
        if action.action_type == "CLARIFY_LAW" and any(k in content for k in ["exist","fake","fabricated","not real"]):
            done = True
            current_state["status"] = "SUCCESS"
    elif current_state["task_level"] == 3:
        if action.action_type == "REQUEST_DOC":
            if current_state["hidden_report"] not in current_state["requested_documents"]:
                current_state["requested_documents"].append(current_state["hidden_report"])
            current_state["status"] = "evidence_received"
        elif action.action_type == "CROSS_EXAMINE" and current_state["current_bac"] in content:
            done = True
            current_state["status"] = "SUCCESS"

    step_count += 1
    if step_count >= 10:
        done = True

    return JSONResponse(content={
        "observation": _obs_dict(),
        "reward": reward,
        "done": done,
        "info": {"status": current_state["status"], "step": step_count}
    })

@app.get("/state")
def get_state():
    return JSONResponse(content=current_state)

@app.get("/tasks")
def list_tasks():
    return JSONResponse(content={"tasks": TASKS})

@app.get("/grader")
async def grader_get():
    return JSONResponse(content={"status": "grader endpoint active", "tasks": [t["id"] for t in TASKS]})

@app.post("/grader")
async def grader_post(request: Request):
    try:
        body = await request.json()
        task_id = body.get("task_id", "task_1_classification")
        action = body.get("action", {})
        # Explicitly pass as keywords for the bulletproof grader
        score = grader_module.grade(action=action, task_id=task_id)
        return JSONResponse(content={"task_id": task_id, "score": score})
    except Exception as e:
        return JSONResponse(content={"task_id": "unknown", "score": 0.05, "error": str(e)})

def main():
    uvicorn.run("server.app:app", host="0.0.0.0", port=7860)

if __name__ == "__main__":
    main()