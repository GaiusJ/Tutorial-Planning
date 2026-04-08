from dataclasses import dataclass, field

import gurobipy as gp
from gurobipy import GRB

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

@dataclass(frozen=True)

class slot:
    day: str
    begin: int
    end: int

@dataclass
class person:
    name: str
    wish_slot: list[slot] = field(default_factory=list)
    alternative_wish_slot: list[slot] = field(default_factory=list)
    block_slots: list[slot] = field(default_factory=list)
    connected: bool = False

persons = [
    person("Person1",
            wish_slot=[
                slot("wednesday", 14, 18),
                slot("wednesday", 10, 12),
                ],
            alternative_wish_slot=[
                 slot("monday", 10, 12),
                 slot("tuesday", 12, 16),
                 slot("thursday", 10, 12),
                ],
            block_slots=[
                slot("monday", 8, 10),
                slot("monday", 12, 18),
                slot("tuesday", 8, 12),
                slot("tuesday", 16, 18),
                slot("wednesday", 8, 10),
                slot("wednesday", 12, 14),
                slot("thursday", 8, 10),
                slot("thursday", 12, 18),
                slot("friday", 8, 18)
            ],
            connected=True),
    person("Person2",
            wish_slot=[
                slot("tuesday", 10, 18),
            ],
            alternative_wish_slot=[
                slot("monday", 14, 16),
                slot("wednesday", 14, 16),
            ],
            block_slots=[
                slot("monday", 8, 14),
                slot("wednesday", 8, 14),
                slot("thursday", 8, 16),
                slot("friday", 8, 16)
            ],
            connected=True),
    person("Person3",
            wish_slot =[
                slot("monday", 8, 10),
                slot("monday", 12, 16),
                slot("tuesday", 8, 12),
                slot("wednesday", 8, 12),
                slot("thursday", 8, 18),
            ],
            alternative_wish_slot=[
                slot("tuesday", 14, 16),
                slot("wednesday", 14, 16),
            ],
            block_slots=[
                slot("monday", 10, 12),
                slot("tuesday", 12, 14),
                slot("tuesday", 16, 18),
                slot("wednesday", 12, 14),
                slot("friday", 8, 18),
            ],
            connected=True),
    person("Person4",
            wish_slot=[
                slot("monday", 10, 14),
            ],
            alternative_wish_slot=[
                slot("tuesday", 12, 16),
                slot("wednesday", 10, 14)
            ],
            block_slots=[
                slot("monday", 8, 10),
                slot("monday", 14, 16),
                slot("tuesday", 8, 10),
                slot("tuesday", 16, 18),
                slot("wednesday", 8, 10),
                slot("wednesday", 14, 16),
                slot("thursday", 8, 18),
                slot("friday", 8, 18)
            ],
            connected=True),
    person("Person5",
            wish_slot=[
                slot("monday", 12, 16),
                slot("tuesday", 10, 14),
                slot("wednesday", 12, 14),
            ],
            alternative_wish_slot =[
                slot("monday", 10, 12),
                slot("tuesday", 14, 18),
                slot("wednesday", 14, 16),
                slot("thursday", 10, 12),
            ],
            block_slots=[
                slot("wednesday", 10, 12),
            ],
            connected=True)
]

lecture = slot("wednesday", 16, 18)
exercise = slot("monday", 16, 18)

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]

# slots are discretized into 2-hour blocks, e.g., 8-10, 10-12, ..., 16-18
all_slots = [
    slot(day, i, i+2)
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]
    for i in range(8, 18, 2)
]

def process_persons(persons: list[person]) -> list[person]:
    processed_persons = []
    for p in persons:
        person_to_process = person(p.name, [], [], [], p.connected)
        for wish in p.wish_slot:
            for i in range(wish.begin, wish.end, 2):
                person_to_process.wish_slot.append(slot(wish.day, i, i + 2))
        for alternative_wish in p.alternative_wish_slot:
            for i in range(alternative_wish.begin, alternative_wish.end, 2):
                person_to_process.alternative_wish_slot.append(slot(alternative_wish.day, i, i + 2))
        for block in p.block_slots:
                for i in range(block.begin, block.end, 2):
                    person_to_process.block_slots.append(slot(block.day, i, i + 2))
        processed_persons.append(person_to_process)

    for p in processed_persons:
        conflicts = set(p.block_slots) & set(p.wish_slot) | set(p.block_slots) & set(p.alternative_wish_slot)
        if conflicts:
            print(f"{p.name}: {conflicts}")
    return processed_persons

def create_and_solve_model(persons: list[person], all_slots: list[slot]):
    model = gp.Model("TutorialPlanning")
    model.Params.OutputFlag = 0
    model.Params.TimeLimit = 60

    min_utility = model.addVar(name="min_utility")

    x = model.addVars([(p.name, s) for p in persons for s in all_slots], vtype=GRB.BINARY, name="x")

    # Constraints
    for s in all_slots:
        model.addConstr(gp.quicksum(x[p.name, s] for p in persons) <= 1, name=f"slot_{s.day}_{s.begin}_{s.end}")

    for p in persons:
        model.addConstr(gp.quicksum(x[p.name, s] for s in all_slots) == 2, name=f"person_{p.name}_Anzahl")

    for p in persons:
        model.addConstr(gp.quicksum(x[p.name, s] for s in p.block_slots) == 0, name=f"person_{p.name}_Block")

    for s in [lecture, exercise]:
        model.addConstr(gp.quicksum(x[p.name, s] for p in persons) == 0, name=f"slot_{s.day}_{s.begin}_{s.end}_lecture_Uebung")

    # helper variable for connectivity bonus
    y = {}
    for p in persons:
        if p.connected:
            for day in DAYS:
                for t in range(8, 16, 2): 
                    y[p.name, day, t] = model.addVar(vtype=GRB.BINARY, name=f"y_{p.name}_{day}_{t}")
                    s1 = slot(day, t, t+2)
                    s2 = slot(day, t+2, t+4)
                    model.addConstr(y[p.name, day, t] <= x[p.name, s1])
                    model.addConstr(y[p.name, day, t] <= x[p.name, s2])

    # calculate utility, weighted: wish = 1, alternative wish = 0.5, connectivity bonus = 2 per connected pair
    Utility = model.addVars([p.name for p in persons], name="Utility")
    for p in persons:
        wish_utility = gp.quicksum(x[p.name, s] for s in p.wish_slot)
        alternative_utility = gp.quicksum(x[p.name, s] for s in p.alternative_wish_slot)
        
        connectivity_bonus = 0
        if p.connected:
            connectivity_bonus = 2 * gp.quicksum(y[p.name, day, t] for day in DAYS for t in range(8, 16, 2))

        model.addConstr(Utility[p.name] == wish_utility + 0.5 * alternative_utility + connectivity_bonus, name=f"Utility_{p.name}")

    # ensure minimum utility
    for p in persons:
        model.addConstr(Utility[p.name] >= min_utility, name=f"MinUtility_{p.name}")

    model.setObjective(gp.quicksum(Utility[p.name] for p in persons) + 10 * min_utility, GRB.MAXIMIZE)

    model.optimize()

    if model.Status == GRB.INFEASIBLE:
        print("Model is infeasible. Computing Irreducible Inconsistent Subsystem (IIS)...")
        model.computeIIS()
        model.write("model.ilp")
        raise RuntimeError("Infeasible model - check model.ilp for conflicts.")
    
    if model.Status not in [GRB.OPTIMAL, GRB.TIME_LIMIT]:
        raise RuntimeError(f"No solution found. Gurobi status: {model.Status}")

    return model, x, Utility, min_utility

def process_solution(x, persons, all_slots):
    solution = {}
    for p in persons:
        solution[p.name] = [s for s in all_slots if x[p.name, s].X > 0.5]
    return solution

def plot_solution(solution, lecture, exercise):
    day_to_x = {day: i for i, day in enumerate(DAYS, start=1)}
    times = list(range(8, 18, 2))
    time_to_y = {time: len(times) - i for i, time in enumerate(times)}

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = plt.colormaps['tab10'].colors
    namen = list(solution.keys())

    for idx, (namen, slots) in enumerate(solution.items()):
        for s in slots:
            x = day_to_x[s.day]
            y = time_to_y[s.begin]
            ax.add_patch(mpatches.Rectangle((x - 0.4, y - 0.4), 0.8, 0.8, color=colors[idx % len(solution)], alpha = 0.7, label=namen))
            ax.text(x, y, namen, ha='center', va='center', fontsize=8)
        
    for slots, label, color in [(lecture, "lecture", 'red'), (exercise, "exercise", 'blue')]:
        x = day_to_x[slots.day]
        y = time_to_y[slots.begin]
        ax.add_patch(mpatches.Rectangle((x - 0.4, y - 0.4), 0.8, 0.8, color=color, alpha=0.7, label=label))
        ax.text(x, y, label, ha='center', va='center', fontsize=8)

    ax.set_xlim(0.5, len(DAYS) + 0.5)
    ax.set_ylim(0.5, len(times) + 0.5)
    ax.set_xticks(range(1, len(DAYS) + 1))
    ax.set_xticklabels(DAYS)
    ax.set_yticks(range(1, len(times) + 1))
    ax.set_yticklabels([f"{t}–{t+2}" for t in reversed(times)])
    ax.set_xlabel("day")
    ax.set_ylabel("time")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    processed = process_persons(persons)
    model, x, Utility, min_utility = create_and_solve_model(processed, all_slots)

    print("\n--- Final Utilities ---")
    for p in processed:
        print(f"{p.name:<20}: {Utility[p.name].X:.1f} Points")
    print(f"{"Minimum Utility:":<20}: {min_utility.X:.1f} Points")

    solution = process_solution(x, processed, all_slots)
    plot_solution(solution, lecture, exercise)