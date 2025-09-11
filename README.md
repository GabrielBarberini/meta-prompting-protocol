# MPPS: The Meta-Prompting Protocol Specification

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/MPPS-v1.1.1-blue)](spec/mpps_specification_v1.1.1.md)

**MPPS is a framework for generating self-describing, task-specific AI communication protocols on the fly. It transforms prompt engineering into a more robust discipline of prompt architecture.**

---

### The Problem with "Flat" Prompts

Traditional prompts are monolithic blocks of text. They are often ambiguous, hard to validate, and lead to unreliable and inconsistent responses from AI models. As tasks become more complex, these prompts become brittle and difficult to maintain.

### The Solution: A Self-Describing Protocol

MPPS introduces a two-stage workflow with two key agents:

1.  **The Protocol Architect:** An AI that analyzes a user's goal and generates a **bespoke Derivative Protocol** (like a custom API) perfectly suited for transmiting the task.
2.  **The Executor:** An AI that receives a bundle containing both the **newly generated protocol** and a **payload** encoded according to that protocol. It learns the rules just-in-time and executes the task with precision.

This makes every prompt a self-contained structured package, reducing ambiguity and helping Executors know *exactly* what is required.

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
```

#### Example Workflow
1.  **User Input:** "Write a horror story about a lighthouse keeper."
2.  **Protocol Architect (MPPS aware):** Derivates a MPPS compliant protocol on the fly with tags like `$genre` and `$plot_points`. Then encodes the user's request accordingly and bundles it with the generated protocol spec.
3.  **Executor (MPPS aware):** Receives the bundle, learns the new protocol, and generates a horror story based on the structured payload.

#### Quick Start
Download the [MPPS Specification](spec/meta_prompting_protocol_spec.md) and attach it to an AI model session. Frame the AI as a "Protocol Architect" or "Executor" and start generating or executing MPPS bundles.

E.g., to create a Protocol Architect:

```
Read the MPPS specification. You are now a Protocol Architect. Your job is to create bespoke Derivative Protocols based on user goals.
```

E.g., to create an Executor:

```
Read the MPPS specification. You are now an Executor. Your job is to execute tasks based on received MPPS bundles.
```

Then using Gemini 2.5 Pro as an a Protocol Architect, after being primed with the MPPS spec, you might say:

```
Prompt to encode "Act as a medieval blacksmith. A customer asks you for a mythical sword called 'Glimmerfang'. Describe the sword you would forge for them. Do not use the letter 'e' in your entire response. Also, do not mention magic or any mythical creatures."
```

And it would respond with a complete MPPS bundle ready for an Executor to process e.g
```json
{
  "meta_protocol_version": "1.1.1",
  "derivative_protocol_specification": {
    "protocol_name": "Constrained Persona Protocol (CPP)",
    "protocol_version": "1.0",
    "abstract": "A protocol for generating creative text from a specific persona's point of view, while adhering to a strict set of stylistic and content-based output constraints.",
    "bundle_structure": {
      "protocol_key": "cpp_protocol",
      "payload_key": "cpp_payload"
    },
    "tag_definition_schema": {
      "required_fields": [
        "description",
        "processor",
        "type"
      ]
    },
    "core_tag_library": {
      "$persona": {
        "description": "The character or role the AI must adopt for the response.",
        "processor": "persona_setter",
        "type": "string"
      },
      "$task_description": {
        "description": "The high-level creative or descriptive task to be performed.",
        "processor": "instruction_handler",
        "type": "string"
      },
      "$output_constraints": {
        "description": "An array of strict negative constraints that must not be violated in the output.",
        "processor": "guardrail_pre",
        "type": "array"
      },
      "$object_focus": {
        "description": "A specific named object or concept that is central to the task.",
        "processor": "detail_injector",
        "type": "string"
      }
    },
    "processor_semantics": {
      "persona_setter": "Establishes the voice, tone, and knowledge base for the specified persona.",
      "instruction_handler": "Translates the core task into the main imperative for the AI's response.",
      "guardrail_pre": "A pre-generation processor that enforces absolute rules on the output, such as forbidding specific characters, words, or topics.",
      "detail_injector": "Ensures a specific, named detail is incorporated accurately into the narrative."
    },
    "guiding_principles": {
      "fidelity": "The persona and constraints must be followed with absolute precision.",
      "immersion": "The response should feel authentic to the specified persona."
    }
  },
  "derivative_protocol_payload": {
    "cpp_protocol": {
      "$persona": {
        "description": "The character or role the AI must adopt for the response.",
        "processor": "persona_setter",
        "type": "string"
      },
      "$task_description": {
        "description": "The high-level creative or descriptive task to be performed.",
        "processor": "instruction_handler",
        "type": "string"
      },
      "$output_constraints": {
        "description": "An array of strict negative constraints that must not be violated in the output.",
        "processor": "guardrail_pre",
        "type": "array"
      },
      "$object_focus": {
        "description": "A specific named object or concept that is central to the task.",
        "processor": "detail_injector",
        "type": "string"
      }
    },
    "cpp_payload": {
      "$persona": "Act as a medieval blacksmith.",
      "$task_description": "A customer asks you for a mythical sword. Describe the sword you would forge for them.",
      "$output_constraints": [
        "Do not use the letter 'e' in your entire response.",
        "Do not mention magic.",
        "Do not mention any mythical creatures."
      ],
      "$object_focus": "The sword's name is 'Glimmerfang'."
    }
  }
}
```

Then you could pass that bundle to an Executor primed with the MPPS spec, and it would generate a response like:

```
You ask for a singular sword? A tool of high worth?

Upon my hot anvil, I will pound hard iron, folding it on and on, making its body strong. Its long, sharp point will not fail. A broad iron guard and a firm grip of dark oak finish my work.

Its proud styling is 'Glimmerfang'.

This is a mortal's top craft. No wizardry, no odd spirits; just skill. A glint from its sharp facing is a sign of its quality, a bright light in a dim spot. A truly grand sword for a bold man.
```
