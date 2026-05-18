"""
CampusPath Backend — FastAPI
Run: uvicorn main:app --reload --port 8000
Requires: pip install fastapi uvicorn pydantic
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json, threading, time, random

app = FastAPI(title="CampusPath API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────
# COURSE DATA
# ─────────────────────────────────────────

COURSES = [
    {"code":"CS101","name":"Intro to CS",        "credits":3,"prereqs":[],                       "seats":30,"cat":"core"},
    {"code":"MA101","name":"Calculus I",           "credits":4,"prereqs":[],                       "seats":35,"cat":"math"},
    {"code":"CS201","name":"Data Structures",      "credits":3,"prereqs":["CS101"],                "seats":25,"cat":"core"},
    {"code":"MA201","name":"Calculus II",           "credits":4,"prereqs":["MA101"],                "seats":28,"cat":"math"},
    {"code":"CS211","name":"Discrete Math",        "credits":3,"prereqs":["MA101"],                "seats":30,"cat":"math"},
    {"code":"CS202","name":"Algorithms",            "credits":3,"prereqs":["CS201","CS211"],        "seats":22,"cat":"core"},
    {"code":"CS301","name":"OS Fundamentals",      "credits":3,"prereqs":["CS201"],                "seats":20,"cat":"core"},
    {"code":"CS302","name":"Database Systems",     "credits":3,"prereqs":["CS201"],                "seats":20,"cat":"core"},
    {"code":"CS303","name":"Computer Networks",    "credits":3,"prereqs":["CS201"],                "seats":18,"cat":"core"},
    {"code":"MA301","name":"Linear Algebra",       "credits":3,"prereqs":["MA201"],                "seats":25,"cat":"math"},
    {"code":"CS311","name":"Theory of Computation","credits":3,"prereqs":["CS202","CS211"],       "seats":18,"cat":"core"},
    {"code":"CS312","name":"Compiler Design",      "credits":3,"prereqs":["CS202","CS301"],       "seats":16,"cat":"elective"},
    {"code":"CS401","name":"ML Fundamentals",      "credits":4,"prereqs":["CS202","MA301"],       "seats":15,"cat":"elective"},
    {"code":"CS402","name":"Distributed Systems",  "credits":3,"prereqs":["CS301","CS303"],       "seats":14,"cat":"elective"},
    {"code":"CS403","name":"Computer Vision",      "credits":3,"prereqs":["CS401"],               "seats":12,"cat":"elective"},
    {"code":"CS404","name":"NLP",                  "credits":3,"prereqs":["CS401"],               "seats":12,"cat":"elective"},
    {"code":"CS450","name":"Software Engineering", "credits":3,"prereqs":["CS302","CS303"],       "seats":18,"cat":"elective"},
    {"code":"CS460","name":"Cybersecurity",        "credits":3,"prereqs":["CS301","CS311"],       "seats":15,"cat":"elective"},
    {"code":"CS480","name":"Parallel Computing",   "credits":3,"prereqs":["CS301","MA301"],       "seats":12,"cat":"elective"},
    {"code":"CS499","name":"Capstone Project",     "credits":3,"prereqs":["CS401","CS450","CS460"],"seats":20,"cat":"core"},
    {"code":"CS500","name":"Universal human values", "credits":1, "prereqs":[],"seats":20,"cat":"core"}
]

course_map = {c["code"]: c for c in COURSES}

# Shared mutable state for race condition demo
_seat_counter = {"value": 10}
_seat_lock = threading.Lock()

# ─────────────────────────────────────────
# GRAPH UTILS
# ─────────────────────────────────────────

def build_adj(courses):
    adj = {c["code"]: [] for c in courses}
    for c in courses:
        for p in c["prereqs"]:
            if p in adj:
                adj[p].append(c["code"])
    return adj


def topo_sort_dfs(codes, adj):
    """DFS-based topological sort — Decrease & Conquer.
    Returns (order, ops_count, log_lines).
    """
    color = {c: "WHITE" for c in codes}
    result, ops, log = [], 0, []

    def dfs(u):
        nonlocal ops
        ops += 1
        color[u] = "GREY"
        log.append(f"  GREY  {u}")
        for v in adj.get(u, []):
            ops += 1
            if color.get(v) == "WHITE":
                dfs(v)
        color[u] = "BLACK"
        log.append(f"  BLACK {u}")
        result.insert(0, u)

    for c in codes:
        if color[c] == "WHITE":
            dfs(c)

    return result, ops, log


def topo_sort_kahns(codes, adj, in_deg_map):
    """Kahn's BFS topological sort.
    Returns (order, ops_count, log_lines).
    """
    from collections import deque
    deg = {c: in_deg_map.get(c, 0) for c in codes}
    queue = deque([c for c in codes if deg[c] == 0])
    result, ops, log = [], 0, []

    while queue:
        ops += 1
        u = queue.popleft()
        result.append(u)
        log.append(f"  DEQUEUE {u} (in-deg=0)")
        for v in adj.get(u, []):
            ops += 1
            deg[v] -= 1
            log.append(f"    {u}→{v}  in-deg[{v}]={deg[v]}")
            if deg[v] == 0:
                queue.append(v)
                log.append(f"    ENQUEUE {v}")

    return result, ops, log


def detect_cycles(courses, extra_edges=None):
    """DFS cycle detection using WHITE/GREY/BLACK colouring.
    Returns list of cycle paths (each path is a list of course codes).
    """
    adj = build_adj(courses)
    if extra_edges:
        for f, t in extra_edges:
            adj.setdefault(f, [])
            if t not in adj[f]:
                adj[f].append(t)

    all_nodes = set(adj.keys())
    for vs in adj.values():
        all_nodes.update(vs)

    color = {n: "WHITE" for n in all_nodes}
    stack = []
    cycles = []
    log = []

    def dfs(u):
        color[u] = "GREY"
        stack.append(u)
        log.append(f"  GREY  {u}")
        for v in adj.get(u, []):
            if color.get(v) == "GREY":
                idx = stack.index(v)
                cycles.append(stack[idx:] + [v])
                log.append(f"  BACK-EDGE {u}→{v}  CYCLE!")
            elif color.get(v, "WHITE") == "WHITE":
                dfs(v)
        color[u] = "BLACK"
        stack.pop()
        log.append(f"  BLACK {u}")

    for n in list(all_nodes):
        if color[n] == "WHITE":
            dfs(n)

    return cycles, log


def group_semesters(order, credit_limit=18):
    semesters = []
    current, used = [], 0
    for code in order:
        c = course_map.get(code)
        if not c:
            continue
        if used + c["credits"] > credit_limit:
            semesters.append(current)
            current, used = [], 0
        current.append({"code": c["code"], "name": c["name"], "credits": c["credits"]})
        used += c["credits"]
    if current:
        semesters.append(current)
    return semesters


# ─────────────────────────────────────────
# PYDANTIC MODELS
# ─────────────────────────────────────────

class TopoRequest(BaseModel):
    algo: str = "both"          # "dfs" | "kahns" | "both"

class PlannerRequest(BaseModel):
    credit_limit: int = 18

class StudentPlanRequest(BaseModel):
    completed: list[str] = []

class CycleRequest(BaseModel):
    extra_edges: list[list[str]] = []  # [["CS305","CS101"], ...]

class RaceRequest(BaseModel):
    threads: int = 10
    initial_seats: int = 10

class SemaphoreRequest(BaseModel):
    threads: int = 8
    seat_capacity: int = 3

class RWLockRequest(BaseModel):
    readers: int = 5
    writers: int = 2


# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "CampusPath API v2.0", "docs": "/docs"}


@app.get("/courses")
def get_courses():
    return {"courses": COURSES, "count": len(COURSES)}


@app.get("/courses/{code}")
def get_course(code: str):
    c = course_map.get(code.upper())
    if not c:
        raise HTTPException(status_code=404, detail=f"Course {code} not found")
    return c


@app.post("/topo")
def run_topo(req: TopoRequest):
    codes = [c["code"] for c in COURSES]
    adj = build_adj(COURSES)
    in_deg = {c: 0 for c in codes}
    for c in COURSES:
        for p in c["prereqs"]:
            if p in in_deg:
                in_deg[c["code"]] += 1

    result = {}

    if req.algo in ("dfs", "both"):
        order, ops, log = topo_sort_dfs(codes, adj)
        result["dfs"] = {
            "order": order,
            "ops": ops,
            "log": log[:60],
            "valid": len(order) == len(codes),
        }

    if req.algo in ("kahns", "both"):
        order, ops, log = topo_sort_kahns(codes, adj, in_deg)
        result["kahns"] = {
            "order": order,
            "ops": ops,
            "log": log[:60],
            "valid": len(order) == len(codes),
        }

    if req.algo == "both" and "dfs" in result and "kahns" in result:
        result["comparison"] = {
            "dfs_ops": result["dfs"]["ops"],
            "kahns_ops": result["kahns"]["ops"],
            "winner": "dfs" if result["dfs"]["ops"] < result["kahns"]["ops"] else "kahns",
            "note": "Both orderings are valid topological sorts. They may differ but both respect all prerequisites.",
        }

    return result


@app.post("/planner")
def run_planner(req: PlannerRequest):
    codes = [c["code"] for c in COURSES]
    adj = build_adj(COURSES)
    order, ops, _ = topo_sort_dfs(codes, adj)
    semesters = group_semesters(order, req.credit_limit)
    total_credits = sum(c["credits"] for c in COURSES)
    return {
        "credit_limit": req.credit_limit,
        "semesters": semesters,
        "semester_count": len(semesters),
        "total_credits": total_credits,
        "topo_ops": ops,
    }


@app.post("/student-plan")
def student_plan(req: StudentPlanRequest):
    completed = set(req.completed)
    remaining = [c for c in COURSES if c["code"] not in completed]
    rem_codes = {c["code"] for c in remaining}

    # Rebuild adj for only remaining courses
    adj2 = {}
    for c in remaining:
        adj2[c["code"]] = [p for p in c["prereqs"] if p in rem_codes]

    # Check prereq violations (completed courses missing their prereqs)
    violations = []
    for code in completed:
        c = course_map.get(code)
        if c:
            missing = [p for p in c["prereqs"] if p not in completed]
            if missing:
                violations.append({"course": code, "missing_prereqs": missing})

    order, ops, _ = topo_sort_dfs(list(rem_codes), adj2)
    semesters = group_semesters(order)

    return {
        "completed": list(completed),
        "remaining_order": order,
        "remaining_count": len(remaining),
        "suggested_semesters": semesters,
        "prereq_violations": violations,
        "ops": ops,
    }


@app.post("/cycles")
def check_cycles(req: CycleRequest):
    cycles, log = detect_cycles(COURSES, req.extra_edges)
    return {
        "has_cycle": len(cycles) > 0,
        "cycle_count": len(cycles),
        "cycles": [{"path": c, "display": " → ".join(c)} for c in cycles],
        "log": log[:80],
        "extra_edges_injected": req.extra_edges,
    }


# ─────────────────────────────────────────
# OS DEMOS
# ─────────────────────────────────────────

@app.post("/os/race")
def race_condition(req: RaceRequest):
    """Simulate a race condition WITHOUT locks.
    Returns a log of interleaved reads/writes showing corruption.
    """
    initial = req.initial_seats
    n = min(req.threads, 20)

    # Simulate unsynchronized access
    shared = [initial]
    log = []
    reads = []

    # Each thread reads then writes — with artificial interleaving
    for i in range(n):
        # Stale read: some threads read the same value
        stale_offset = random.choice([0, 0, 0, 1, 2])
        read_val = shared[0] + stale_offset
        reads.append(read_val)
        log.append({
            "thread": f"T-{i}",
            "action": "READ",
            "value": read_val,
            "note": "stale" if stale_offset > 0 else "fresh",
        })

    for i in range(n):
        write_val = reads[i] - 1
        shared[0] = write_val
        log.append({
            "thread": f"T-{i}",
            "action": "WRITE",
            "value": write_val,
        })

    expected = initial - n
    final = shared[0]
    return {
        "initial_seats": initial,
        "threads": n,
        "expected_final": expected,
        "actual_final": final,
        "corrupted": final != expected,
        "seats_lost": final - expected,
        "log": log,
    }


@app.post("/os/semaphore")
def semaphore_demo(req: SemaphoreRequest):
    """Simulate counting semaphore — correct seat management."""
    capacity = req.seat_capacity
    n = req.threads
    log = []
    avail = [capacity]
    blocked_queue = []
    final_seats = [capacity]

    events = []
    for i in range(n):
        events.append({"t": i * 0.15 + random.uniform(0, 0.05), "thread": i, "type": "try"})
    events.sort(key=lambda e: e["t"])

    for ev in events:
        tid = f"T-{ev['thread']}"
        if avail[0] > 0:
            avail[0] -= 1
            final_seats[0] = avail[0]
            log.append({"thread": tid, "action": "ACQUIRED", "remaining": avail[0]})
        else:
            blocked_queue.append(tid)
            log.append({"thread": tid, "action": "BLOCKED", "remaining": 0})

        # Simulate release after some time
        if random.random() < 0.6 and len(blocked_queue) > 0:
            avail[0] += 1
            released = blocked_queue.pop(0)
            avail[0] -= 1
            log.append({"thread": released, "action": "UNBLOCKED_ACQUIRED", "remaining": avail[0]})

    return {
        "capacity": capacity,
        "threads": n,
        "final_available": avail[0],
        "blocked_at_end": blocked_queue,
        "log": log,
        "correct": True,
        "note": "Semaphore guaranteed no seat count ever went negative.",
    }


@app.post("/os/rwlock")
def rwlock_demo(req: RWLockRequest):
    """Simulate Reader-Writer Lock via threading.Condition pattern."""
    events = []
    t = 0
    # Readers
    for i in range(req.readers):
        start = t + random.uniform(0, 0.3)
        duration = random.uniform(0.2, 0.6)
        events.append({"thread": f"R-{i}", "type": "reader", "start": round(start,2), "end": round(start+duration,2)})
        t += 0.1

    # Writers — must wait for all readers
    for i in range(req.writers):
        writer_start = t + random.uniform(0.1, 0.4)
        events.append({"thread": f"W-{i}", "type": "writer", "start": round(writer_start,2), "end": round(writer_start+0.3,2)})
        t += 0.4

    events.sort(key=lambda e: e["start"])

    log = []
    active_readers = 0
    for ev in events:
        if ev["type"] == "reader":
            active_readers += 1
            log.append({"thread": ev["thread"], "action": "START_READ", "active_readers": active_readers, "at": ev["start"]})
            active_readers = max(0, active_readers - 1)
            log.append({"thread": ev["thread"], "action": "END_READ", "active_readers": active_readers, "at": ev["end"]})
        else:
            log.append({"thread": ev["thread"], "action": "WAITING_FOR_READERS", "active_readers": active_readers, "at": ev["start"]})
            log.append({"thread": ev["thread"], "action": "WRITE_START", "active_readers": 0, "at": ev["start"]+0.05})
            log.append({"thread": ev["thread"], "action": "WRITE_END", "active_readers": 0, "at": ev["end"]})

    return {
        "readers": req.readers,
        "writers": req.writers,
        "events": log,
        "note": "Multiple concurrent readers; writer gets exclusive access only when readers=0.",
    }


# ─────────────────────────────────────────
# STATS ENDPOINT
# ─────────────────────────────────────────

@app.get("/stats")
def stats():
    total_credits = sum(c["credits"] for c in COURSES)
    total_edges = sum(len(c["prereqs"]) for c in COURSES)
    cats = {}
    for c in COURSES:
        cats[c["cat"]] = cats.get(c["cat"], 0) + 1
    return {
        "total_courses": len(COURSES),
        "total_edges": total_edges,
        "total_credits": total_credits,
        "by_category": cats,
    }
