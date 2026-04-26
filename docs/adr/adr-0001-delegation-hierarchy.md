# ADR-0001: Generalize Y-axis as Arbitrarily Expandable Delegation Hierarchy

**Status:** Proposed  
**Date:** 2026-04-26  
**Issue:** #13

## Context

The current Y-axis uses three fixed roles: Stakeholder, User, and Engineer. These labels are useful defaults for technical change management projects but are a specific instantiation of a more general pattern.

What the tiers actually represent is a delegation hierarchy — each tier translates the tier above it into more concrete, executable terms. The number of tiers needed is a function of the problem's complexity and scale, not a fixed property of the framework.

Pressure points that surface this:

- A project requiring vendor delegation would benefit from a 4th tier between Engineer and execution
- Purely operational workflows (no system changes) may need only 2 tiers
- The label "Engineer" implies technical work, but the bottom tier is more precisely "the layer at which work becomes directly executable" — applicable to any domain

The current data model enforces roles as a schema constraint (`CHECK(role IN ('stakeholder','user','engineer'))`), making generalization a non-trivial change.

## Decision

Not yet made. Under consideration.

Options on the table:

**Option A — Variable tiers, user-defined labels**  
Roles become project-defined rather than schema-enforced. Sensible defaults (Stakeholder / User / Engineer) are offered at project creation but fully customizable. The matrix expands or contracts based on the number of tiers declared.

**Option B — Fixed 3 tiers, clarified semantics**  
Keep the current 3-row structure but reframe the labels in documentation to reflect the delegation hierarchy concept. "Engineer" becomes "Execution layer" or equivalent. Simpler, but loses the extensibility.

**Option C — Fixed tiers with an escape hatch**  
Keep 3 fixed tiers but allow a 4th "extended" tier for overflow delegation (e.g. vendor relationships). A limited compromise.

## Consequences

**If Option A is chosen:**
- Data model change required: roles must become project-defined, removing the schema CHECK constraint
- UI generalization required: step navigation, matrix columns, and role labels are currently hardcoded to 3 roles
- Dependency vocabulary (requires/enables/prerequisites) is role-agnostic and unaffected
- Topological sort and contradiction detection operate on work items, not roles — likely unaffected
- Opens the door to KRM applied to purely operational workflows (no engineered states in the technical sense)
- Risk: variable tier count may make the matrix unreadable beyond 4-5 tiers

**If Option B is chosen:**
- No code changes required
- Framework documentation updated to clarify tier semantics
- Loses extensibility; projects requiring vendor delegation must model it within existing tiers

**If Option C is chosen:**
- Moderate data model change
- Lower generalization risk than Option A
- May feel like a half-measure that satisfies neither constraint

## Open Questions

- What is the right term for "tier"? Row, layer, delegation level? To be settled before implementation.
- Is there a practical ceiling on tier count before the matrix becomes unreadable?
- Does the operational workflow use case (KRM applied to non-technical processes) follow naturally from this generalization, or does it introduce complexity that argues for keeping tiers static?
