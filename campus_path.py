"""
╔══════════════════════════════════════════════════════════════╗
║          CampusPath: Smart Course Prerequisite Planner       ║
║  DAA: Topological Sort (DFS / Decrease-and-Conquer)          ║
║  OS:  Process Synchronization & Race Condition Demo          ║
╚══════════════════════════════════════════════════════════════╝
"""

import json
import threading
import time
import random
from collections import defaultdict

# ─────────────────────────────────────────────────────────────
#  1. GRAPH: Load curriculum from config file
# ─────────────────────────────────────────────────────────────

class CourseGraph:
    """Directed Acyclic Graph of courses and their prerequisites."""

    def __init__(self, config_path: str = "courses.json"):
        with open(config_path) as f:
            data = json.load(f)

        self.courses: dict[str, dict] = {}   # id → course info
        self.adj: dict[str, list[str]] = {}  # id → [successors]  (course → courses that need it)
        self.prereq: dict[str, list[str]] = {}  # id → [prerequisites]

        for c in data["courses"]:
            cid = c["id"]
            self.courses[cid] = c
            self.prereq[cid] = c.get("prerequisites", [])
            self.adj[cid] = []  # filled below
            if cid not in self.adj:
                self.adj[cid] = []

        # Build adjacency list: prereq → course  (directed edge)
        for cid, prereqs in self.prereq.items():
            for p in prereqs:
                self.adj[p].append(cid)

        # Seat counters (shared mutable state – used for OS demo)
        self.seats: dict[str, int] = {cid: c["seats"] for cid, c in self.courses.items()}

    def course_name(self, cid: str) -> str:
        return self.courses[cid]["name"]

    def all_ids(self) -> list[str]:
        return list(self.courses.keys())


# ─────────────────────────────────────────────────────────────
#  2. DAA: Topological Sort via DFS (Decrease-and-Conquer)
# ─────────────────────────────────────────────────────────────

class TopologicalSorter:
    """
    DFS-based Topological Sort (Decrease-and-Conquer paradigm).

    Decrease-and-Conquer idea:
      • Decrease: recurse into a node's prerequisites first.
      • Conquer:  post-order append → guarantees prerequisites precede dependents.

    Also performs cycle detection (impossible prerequisite loops).
    """

    WHITE, GRAY, BLACK = 0, 1, 2  # DFS colour states

    def __init__(self, graph: CourseGraph):
        self.graph = graph

    def sort(self, subset: list[str] | None = None) -> tuple[list[str], list[str]]:
        """
        Returns (order, cycle_path).
        order     – valid completion sequence (empty if cycle found)
        cycle_path – the cycle (empty if no cycle)
        """
        nodes = subset if subset is not None else self.graph.all_ids()
        colour = {n: self.WHITE for n in nodes}
        stack: list[str] = []
        parent: dict[str, str | None] = {n: None for n in nodes}

        cycle_path: list[str] = []

        def dfs(u: str) -> bool:
            """Returns True if a cycle was found."""
            colour[u] = self.GRAY
            for v in self.graph.adj.get(u, []):
                if v not in colour:
                    continue  # v is outside the requested subset
                if colour[v] == self.GRAY:
                    # Back-edge detected → cycle!
                    cycle_path.clear()
                    # Trace cycle
                    cycle_path.append(v)
                    cur = u
                    while cur != v:
                        cycle_path.append(cur)
                        cur = parent[cur]
                    cycle_path.append(v)
                    cycle_path.reverse()
                    return True
                if colour[v] == self.WHITE:
                    parent[v] = u
                    if dfs(v):
                        return True
            colour[u] = self.BLACK
            stack.append(u)
            return False

        for node in nodes:
            if colour[node] == self.WHITE:
                if dfs(node):
                    return [], cycle_path

        return stack, []   # stack is already in topological order

    def personalised_plan(
        self,
        target_courses: list[str],
        completed: list[str]
    ) -> tuple[list[str], list[str]]:
        """
        Generate a plan for `target_courses` excluding already-completed ones.
        Collects all transitive prerequisites, then runs topo-sort on that subgraph.
        """
        # BFS/DFS to collect all prerequisites of target courses
        needed: set[str] = set()
        queue = list(target_courses)
        while queue:
            c = queue.pop()
            if c in completed or c in needed:
                continue
            needed.add(c)
            queue.extend(self.graph.prereq.get(c, []))

        needed -= set(completed)
        return self.sort(list(needed))

    def group_into_semesters(
        self,
        order: list[str],
        credit_limit: int = 18
    ) -> list[list[str]]:
        """
        BONUS: Group topologically sorted courses into semesters
        respecting a credit-per-semester limit.
        A course can be placed in a semester only after all its
        prerequisites are in earlier semesters.
        """
        placed: set[str] = set()
        semesters: list[list[str]] = []

        remaining = list(order)
        while remaining:
            sem: list[str] = []
            sem_credits = 0
            next_remaining = []
            for cid in remaining:
                prereqs_done = all(p in placed for p in self.graph.prereq.get(cid, []))
                credits = self.graph.courses[cid]["credits"]
                if prereqs_done and sem_credits + credits <= credit_limit:
                    sem.append(cid)
                    sem_credits += credits
                else:
                    next_remaining.append(cid)
            if not sem:
                # Safety: place first course to avoid infinite loop
                sem.append(next_remaining.pop(0))
                next_remaining = [c for c in next_remaining if c not in sem]
            placed.update(sem)
            semesters.append(sem)
            remaining = next_remaining

        return semesters


# ─────────────────────────────────────────────────────────────
#  3. OS: Concurrent Registration – Race Condition Demo
# ─────────────────────────────────────────────────────────────

class RegistrationSystem:
    """
    Simulates N students registering for courses concurrently.

    MODE A (unsafe)  – no lock  → race conditions possible
    MODE B (safe)    – mutex lock per course → correct behaviour
    """

    def __init__(self, graph: CourseGraph):
        self.graph = graph
        self.lock_table: dict[str, threading.Lock] = {
            cid: threading.Lock() for cid in graph.all_ids()
        }
        self.log: list[str] = []
        self._log_lock = threading.Lock()

    def _log(self, msg: str):
        with self._log_lock:
            self.log.append(msg)

    # ── UNSAFE registration (no synchronisation) ──────────────
    def _register_unsafe(self, student: str, course: str):
        seats = self.graph.seats[course]
        time.sleep(random.uniform(0.001, 0.005))  # simulate I/O delay
        if seats > 0:
            time.sleep(random.uniform(0.001, 0.003))  # simulate write delay
            self.graph.seats[course] = seats - 1      # non-atomic read-modify-write!
            self._log(f"  [UNSAFE] {student} registered for {course}  (seats left: {self.graph.seats[course]})")
        else:
            self._log(f"  [UNSAFE] {student} FAILED – {course} full")

    # ── SAFE registration (mutex lock per course) ─────────────
    def _register_safe(self, student: str, course: str):
        lock = self.lock_table[course]
        lock.acquire()                                # ← CRITICAL SECTION entry
        try:
            if self.graph.seats[course] > 0:
                time.sleep(random.uniform(0.001, 0.003))
                self.graph.seats[course] -= 1
                self._log(f"  [SAFE]   {student} registered for {course}  (seats left: {self.graph.seats[course]})")
            else:
                self._log(f"  [SAFE]   {student} FAILED – {course} full")
        finally:
            lock.release()                            # ← CRITICAL SECTION exit

    def run_demo(self, course: str, n_students: int = 8, mode: str = "unsafe"):
        """Spawn n_students threads all trying to register for the same course."""
        self.graph.seats[course] = 3   # Reset to 3 seats for the demo
        self.log.clear()
        students = [f"S{i+1:02d}" for i in range(n_students)]
        threads = []

        fn = self._register_unsafe if mode == "unsafe" else self._register_safe

        for s in students:
            t = threading.Thread(target=fn, args=(s, course))
            threads.append(t)

        # Start all threads as close together as possible
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final_seats = self.graph.seats[course]
        registered  = 3 - final_seats   # how many the system thinks registered
        actual_count = sum(1 for l in self.log if "registered" in l and "[" + mode.upper() + "]" in l)

        return {
            "mode": mode,
            "course": course,
            "initial_seats": 3,
            "final_seats_counter": final_seats,
            "log": self.log[:],
            "warning": None if final_seats >= 0 else "⚠️  Counter went NEGATIVE — race condition!",
            "anomaly": final_seats < 0 or registered != actual_count,
        }


# ─────────────────────────────────────────────────────────────
#  4. MAIN DEMO – puts it all together
# ─────────────────────────────────────────────────────────────

def print_banner(title: str):
    width = 62
    print("\n" + "═" * width)
    print(f"  {title}")
    print("═" * width)

def print_section(title: str):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


def main():
    graph = CourseGraph("courses.json")
    sorter = TopologicalSorter(graph)
    registry = RegistrationSystem(graph)

    print_banner("🎓  CampusPath: Smart Course Prerequisite Planner")

    # ── A. Full curriculum topological sort ───────────────────
    print_section("A. Full Curriculum – Topological Order")
    order, cycle = sorter.sort()
    if cycle:
        print(f"  ❌ Cycle detected: {' → '.join(cycle)}")
    else:
        print(f"  ✅ Valid completion order ({len(order)} courses):\n")
        for i, cid in enumerate(order, 1):
            name = graph.course_name(cid)
            prereqs = graph.prereq[cid]
            prereq_str = ", ".join(prereqs) if prereqs else "none"
            print(f"  {i:>2}. {cid:<10} {name:<35} prereqs: [{prereq_str}]")

    # ── B. Cycle detection demo ───────────────────────────────
    print_section("B. Cycle Detection – Injecting an Impossible Loop")
    # Temporarily inject a cycle: CS101 requires CS404 (which depends on CS101 chain)
    graph.prereq["CS101"].append("CS404")
    graph.adj["CS404"].append("CS101")
    bad_order, cycle = sorter.sort()
    if cycle:
        print(f"  ❌ Cycle detected! Impossible configuration:")
        print(f"     {' → '.join(cycle)}")
    # Remove the fake cycle
    graph.prereq["CS101"].remove("CS404")
    graph.adj["CS404"].remove("CS101")
    print("  ✅ Cycle removed. Graph is valid again.\n")

    # ── C. Personalised plan ──────────────────────────────────
    print_section("C. Personalised Plan  [Bonus Feature]")
    completed = ["CS101", "CS102", "CS103", "MATH101", "MATH102", "MATH201"]
    targets   = ["CS405", "CS404"]
    print(f"  Completed: {completed}")
    print(f"  Targets  : {targets}\n")
    plan, cyc = sorter.personalised_plan(targets, completed)
    if cyc:
        print(f"  ❌ Cycle: {' → '.join(cyc)}")
    else:
        print(f"  Remaining courses in order:")
        for i, cid in enumerate(plan, 1):
            print(f"    {i}. {cid:<10} {graph.course_name(cid)}")

    # ── D. Semester grouping ──────────────────────────────────
    print_section("D. Semester-by-Semester Layout  [Bonus Feature]")
    full_order, _ = sorter.sort()
    semesters = sorter.group_into_semesters(full_order, credit_limit=15)
    for i, sem in enumerate(semesters, 1):
        total_credits = sum(graph.courses[c]["credits"] for c in sem)
        print(f"\n  Semester {i}  ({total_credits} credits)")
        for cid in sem:
            c = graph.courses[cid]
            print(f"    • {cid:<10} {c['name']:<35} ({c['credits']} cr)")

    # ── E. OS: Race Condition Demo ────────────────────────────
    print_section("E. Concurrency Demo – Race Condition (8 students, 3 seats)")
    course_demo = "CS201"
    print(f"  Course: {course_demo} – {graph.course_name(course_demo)}")

    print(f"\n  [MODE: UNSAFE – No synchronisation]")
    result_unsafe = registry.run_demo(course_demo, n_students=8, mode="unsafe")
    for line in result_unsafe["log"]:
        print(line)
    print(f"\n  Final seat counter : {result_unsafe['final_seats_counter']}")
    if result_unsafe["warning"]:
        print(f"  {result_unsafe['warning']}")
    if result_unsafe["anomaly"]:
        print("  ⚠️  DATA CORRUPTION DETECTED – seat counter is unreliable!")

    print(f"\n  [MODE: SAFE – Mutex Lock per Course]")
    result_safe = registry.run_demo(course_demo, n_students=8, mode="safe")
    for line in result_safe["log"]:
        print(line)
    print(f"\n  Final seat counter : {result_safe['final_seats_counter']}")
    if not result_safe["anomaly"]:
        print("  ✅ Correct! At most 3 students registered. No corruption.")

    print("\n" + "═"*62)
    print("  CampusPath demo complete.")
    print("═"*62 + "\n")


if __name__ == "__main__":
    main()
