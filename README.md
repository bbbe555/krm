# KRM — Kinetic Requirements Model

## What This Is

KRM (Kinetic Requirements Model) is a requirements capture and dependency management framework built to surface the work hidden inside change. It evolved from a practical migration project into a general-purpose tool for managing complex transitions.

The core insight: most requirements frameworks capture *what* needs to happen but not *why things are in the order they're in* or *what breaks if something is missing*. KRM makes dependencies explicit, surfaces contradictions automatically, and generates executable procedures from the dependency graph rather than requiring them to be authored separately.

The framework and the tool were developed together in a single long conversation, each informing the other. The tool is currently at **v5.8**.

## The Framework

### Core Structure

A 3×3 matrix (minimum, infinitely expandable):

- **X-axis (State):** Current → Kinetic → Desired
- **Y-axis (Role):** Owner/Stakeholder → User → Engineer

### Key Concepts

**States** — conditions of the world, true or false. "User account is provisioned in the target system." You can point at the world and ask if it's true. States are declarative, not imperative.

**Work Items** — the ordered sequence of conditions that must become true to achieve engineered states. Also expressed as states ("X is [condition]"), not as tasks ("do X"). Work — the actual execution — happens outside the tool in response to a condition not yet being true.

**Engineered States** — what must be technically true for user stories to be achievable. One end state per entry. Not implementation steps.

**Revelation Cascade** — each story in the current state reveals the desired state, which reveals the kinetic state required to achieve it. The matrix is interrogated, not authored top-down.

**Story Resolution Rule** — a story at any row is correctly scoped when it describes exactly one state change, is expressible in one sentence, and its acceptance criterion can be evaluated by someone operating at that row's level of abstraction without knowledge of the rows above or below it.

**Requires / Enables** — the two directional dependency relationships:
- Engineered state *requires* work items (state → work, downward)
- Work item *enables* engineered states (work → state, upward)
- Work item has *prerequisites* — other work items that must be true first (lateral, establishes execution order)

**Prerequisite** — a work item to work item relationship establishing linearity. Item A has a prerequisite B when B must be true before A can proceed.

**Topological Sort** — Kahn's algorithm over the prerequisite graph produces a derived execution order. This is the procedure — not authored, derived. Cycle detection surfaces contradictions automatically.

**Promote & Split** — when a work item can't have a single acceptance criterion because it's actually a category of work, it gets promoted to an engineered state and its children become new work items. Signal: you cannot write a single acceptance criterion.

**Add Prerequisite** — when writing an acceptance criterion reveals a missing upstream dependency, insert it before the blocked item. The blocked item stays; the prerequisite is inserted above it.

**Milestone Markers** — derived from the topology. After the last work item that enables a given engineered state in the execution order, a milestone marker appears. Blue = state completable. Green = state achieved. No manual grouping required.

**Tags** — free-form, comma-separated labels on work items. User-defined. Used to filter the execution order and generate role/phase-specific procedure exports.

### Dependency Vocabulary (final settled terms)

| Relationship | Direction | Display |
|---|---|---|
| State requires work items | State → Work | "requires N work items" on state |
| Work item enables states | Work → State | "Enables: #1 #3" on work item |
| Work item has prerequisites | Work → Work | "Prerequisites" selector in edit modal |

### What the Kinetic View Shows

1. **Contradictions & Gaps** — cycles (⛔ error), orphaned states (⚠ no work items), orphaned work items (⚠ not connected to any state), unreachable states
2. **Derived Execution Order** — topologically sorted, with milestone markers inline when engineered states become completable/achieved, unanchored items flagged
3. **State Completion** — per-state progress bars showing closed/total work items
4. **Tag filter** — filter execution order by any tag in use
5. **Procedure export** — markdown runbook, all items or filtered by tag

## The Application (v5.8)

### Stack
- **Backend:** Python / FastAPI / SQLite
- **Frontend:** Single HTML file, vanilla JS, no framework
- **Deployment:** Docker + docker-compose
- **Port:** 8100 (configurable in docker-compose.yml)

### Data Model (SQLite)

```
projects (id, name, description, created_at, updated_at)

cells (id, project_id, state[current|kinetic|desired], role[stakeholder|user|engineer],
       story, scope_gate, updated_at)

queue_items (id, cell_id, order_num, description, status, notes, updated_at)
```

**Status values:** pending, active, closed, deferred, blocked

**Notes field encoding** (all internal metadata stored in the notes field as space-separated tags):
- `ac:<text>` — acceptance criterion
- `declared:<ids>` — engineered state IDs this work item enables (upfront declaration)
- `covers:<ids>` — engineered state IDs confirmed at closure
- `upstream_for:<id>` — this item is a prerequisite for item <id>
- `split_from:<id>` — this item was split from engineered state <id>
- `tags:<comma-separated>` — user-defined tags
- `promoted` — item was promoted from work item to engineered state

### Cell mapping to UI concepts

| Cell | UI Location |
|---|---|
| desired.stakeholder | Anchor States — Desired |
| current.stakeholder | Anchor States — Current |
| kinetic.stakeholder | Anchor States — Kinetic |
| desired.user | User States — Desired (list) |
| current.user | User States — Current (list) |
| kinetic.user | User States — Kinetic (list) |
| desired.engineer | Engineered States (left panel) |
| kinetic.engineer | Work Items / Yield Queue (right panel) |

### Navigation Structure

**View tab** — top-down 3×3 matrix. Every cell is clickable. Opens appropriate editor (single sentence, list builder, or queue editor).

**Refine tab** — step-by-step guided workflow:
- Anchor States (Step 1) — all three stakeholder cells side by side
- User States (Step 2) — all three user cells as list builders
- Engineered States (Step 3) — left panel: engineered states list, right panel: work items queue with full editor
- Kinetic (Step 4) — analysis view with topological sort, contradiction detection, procedure export

### Work Item Edit Modal Fields
1. Description
2. Load-bearing for engineered states (multi-select — declares enables relationship upfront)
3. Prerequisites (multi-select — other work items that must be true first)
4. Acceptance Criterion
5. Status (dropdown: pending/active/closed/deferred/blocked)
6. Satisfies engineered states (multi-select — confirms enables at closure, shown when status = closed)
7. Tags (free text, comma-separated, existing tags shown as clickable chips)
8. Notes

### Restructuring Gestures (in work item editor)
- **⬆ Promote & Split** — item is at wrong level of abstraction. Moves to engineered states, opens list builder to enumerate children. Signal: can't write a single acceptance criterion.
- **⬅ Add Prerequisite** — item revealed a missing upstream dependency. Opens list builder, inserts items before the blocked item. State is preserved across the modal swap.

### Deployment

```bash
# Deploy / redeploy function (paste into shell)
krm-redeploy() {
  local APP_DIR="$HOME/Downloads/krm-app"
  local ZIP=$(ls -t "$HOME/Downloads"/krm-app-v*.zip 2>/dev/null | head -1)
  if [[ -z "$ZIP" ]]; then echo "✗ No krm-app-v*.zip found"; return 1; fi
  local VERSION=$(echo "$ZIP" | grep -o 'v[0-9.]*' | head -1)
  docker compose -f "$APP_DIR/docker-compose.yml" down 2>/dev/null
  docker rmi krm-app-krm 2>/dev/null
  rm -rf "$APP_DIR"
  unzip -o "$ZIP" -d "$HOME/Downloads" > /dev/null
  mv "$ZIP" "$APP_DIR/krm-app-$VERSION.zip"
  docker compose -f "$APP_DIR/docker-compose.yml" up -d --build
  echo "✓ KRM $VERSION running — http://localhost:8100"
}
```

Data persists in Docker volume `krm-app_krm-data` at `/data/krm.db` inside the container. Survives rebuilds as long as volume is not deleted.

## Design Decisions & Rationale

**Why SQLite not Postgres** — minimal stack, easy to federate later. One file, zero config. Decision made early, still correct.

**Why single HTML file frontend** — no build step, no framework overhead. Everything ships in one file. Tradeoff: file is large (~3000 lines), patching requires care.

**Why notes field encoding** — avoids schema migrations for metadata that's still evolving. Downside: parsing logic is distributed across the frontend. Will need refactoring when schema stabilizes.

**Why work items are states not tasks** — the most important discipline in the framework. A work item describes a condition of the world (true or false). The work that makes it true lives outside the tool. This keeps the tool focused on requirements and dependency, not project management.

**Why topological sort not manual ordering** — manual ordering breaks when dependencies are added. Derived order is always consistent with declared prerequisites. The user declares relationships; the tool derives sequence.

**Why tags are free-form not taxonomized** — premature taxonomy forces decisions before the problem space is understood. Tags emerge from use. Taxonomy can be imposed later once patterns are visible.

**Why scope gate was removed from user desired row** — the scope gate at the engineer row does the real work. At the user row, the list you write is already your scoped set. The gate question ("which of these, if absent, breaks the parent story?") returns "all of them" for a well-formed list. The step added friction without value.

**Why user current state was removed as a step** — mechanical inversion of desired state with platform swapped. Adds no cognitive value when the gap is already described by the stakeholder states.

**Piston/cylinder metaphor** — the scope gate is the cylinder wall, the yield queue is the crankshaft. Controlled explosion, directed force, sequential strokes. Explosion is necessary and generative; the scope gate makes it a piston rather than a grenade. (Acknowledged as potentially cringe, retained because it's load-bearing.)

## Relationship to Existing Frameworks

| Framework | Overlap | Gap |
|---|---|---|
| Three-Horizon Model | X-axis structure | No role layering, not requirements-oriented |
| Cynefin | Context-dependent revelation | No structural matrix |
| Jobs-to-be-Done | User desired state framing | No state progression |
| BDD / Given-When-Then | Engineer row mechanics | Flat, no upward propagation |
| Story Mapping (Patton) | Two-axis structure | Sequencing delivery, not state revelation |
| SAFe | Story decomposition | No dependency graph, no contradiction detection |
| State Machine Modeling | X-axis formalism | Not applied to stakeholder-stratified requirements |

**KRM's defensible novelty:** topological sort over a stakeholder-stratified state matrix, with requires/enables/prerequisite dependency vocabulary, milestone clustering derived from the graph, and contradiction detection as a first-class feature. The synthesis is the contribution.

**The agile insight:** most agile shops don't refactor stories well because the tooling makes restructuring expensive. Promote & Split collapses the recognition and restructuring into a single gesture at the moment of realization. The correct behavior becomes the path of least resistance.

## Tabled Items (Open Issues)

### P1 — Foundation

**Import JSON** — load a project snapshot from a JSON file. Prerequisite for synthetic data work and portability. Export already exists; import is the missing half.

**GitHub integration** — move code to GitHub repo, wire Claude to repo via MCP connector. Replace zip-file workflow with pull-and-rebuild.

### P2 — Synthetic Data

**Layered synthetic dataset** — a fictional but realistic project structured in four layers:
1. Initial coherent state — looks complete, passes contradiction detection
2. First revelation — one constraint invalidates an assumption, triggers cascade
3. Second revelation — creates a genuine contradiction with existing dependency
4. Stabilization — resolved state after absorbing both revelations

Purpose: test whether KRM can absorb emergent requirements without breaking the model. The most important test of the framework's real-world value.

### P3 — Rendering & Export

**Procedure export refinement** — currently exports a flat markdown list. Should render as a proper numbered runbook with milestone markers as chapter breaks, verification steps inline, and grouped by tag filter. The matrix should generate the procedure, not require it to be authored separately.

**Dependency visualization** — SVG thread overlay on the View matrix. Lines connecting work items to engineered states, thickening where dependencies converge, colored by status. The "sense of motion" in the View matrix made explicit as drawn threads.

**State-to-state ordering** — engineered states have implicit sequence not currently modeled. A lightweight ordering mechanism (drag-reorder or explicit prereq declaration at the state level) would make milestone clustering more accurate.

### P4 — Onboarding & Taxonomy

**Tag taxonomy prompt at project creation** — before entering any states, prompt the user to name their organizational axes. Phase? Owner? System domain? Suggest defaults (phase-1, phase-2, day-1). Free-form additions. Makes tag filtering useful from the start rather than retroactively.

**Project creation onboarding flow** — currently a blank modal. Should walk through: name the project, identify the stakeholder, anchor the desired state, name the major phases. Five minutes of structured input that seeds the matrix correctly.

### P5 — Intelligence

**AI interrogation of entered text** — Claude API call that evaluates whether entered text describes a state or a work item, flags violations inline, suggests rewrites. Binary classification: "is this a condition of the world (true/false) or an action to be performed?" High accuracy, low token cost. Contingent on framework being proven on real projects first.

**Semantic clustering** — items that share prerequisite chains and enable the same engineered states form natural clusters. Render derived clusters in the Kinetic view as named groups, not just milestone markers. The dependency graph IS the taxonomy.

## Version History (brief)

- v1.x — initial guided step-by-step workflow
- v2.x — yield queue, acceptance criteria, promote/split, upstream dependency
- v3.x — View/Refine tabs, top-down matrix view, editable cells from matrix
- v4.x — combined Engineered States + Work Items surface, requires/enables vocabulary, dependency highlighting
- v5.x — topological sort, contradiction detection, milestone markers, tags, procedure export

Current: **v5.8**

## GitHub Migration Plan

1. Create repo in personal GitHub account (suggested name: `krm` or `kinetic-requirements-model`)
2. Initial commit: v5.8 code (backend/main.py, frontend/index.html, Dockerfile, docker-compose.yml, README.md)
3. Connect GitHub MCP connector in Claude project settings
4. Open issues for all tabled items above
5. Future work: Claude pushes changes directly to repo, you pull and rebuild

The conversation thread remains useful for design discussion. The repo becomes the execution surface. Issues replace the tabled items list in this document.

