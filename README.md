# MPPS: The Meta-Prompting Protocol Specification

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/MPPS-v1.1.1-blue)](spec/mpps_specification_v1.1.1.md)

**MPPS is a framework for generating self-describing, task-specific AI communication protocols on the fly. It transforms prompt engineering into a more robust discipline of prompt architecture.**

---

### The Problem with "Flat" Prompts

Traditional prompts are monolithic blocks of text. They are often ambiguous, hard to validate, and lead to unreliable and inconsistent responses from AI models. As tasks become more complex, these prompts become brittle and difficult to maintain.

### The Solution: A Self-Describing Protocol

MPPS introduces a two-stage workflow with two key agents:

1.  **The Protocol Architect:** An AI that analyzes a user's goal and generates a **bespoke Derivative Protocol** (like a custom API) perfectly suited for the task.
2.  **The Executor:** An AI that receives a bundle containing both the **newly generated protocol** and a **payload** encoded according to that protocol. It learns the rules just-in-time and executes the task with precision.

This makes every prompt a self-contained, machine-readable package, eliminating ambiguity and ensuring the Executor knows *exactly* what is required.

### How It Works: A Quick Look

An MPPS bundle contains the full rulebook alongside the data.

```json
{
  "derivative_protocol_specification": {
    "protocol_name": "Creative Writing Protocol (CWP)",
    "core_tag_library": {
      "$genre": { "..." },
      "$plot_points": { "..." }
    },
    "...": "..."
  },
  "derivative_protocol_payload": {
    "$genre": "Horror",
    "$plot_points": ["A lone lighthouse keeper...", "..."]
  }
}
