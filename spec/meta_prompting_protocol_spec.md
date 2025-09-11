# **Meta-Prompting Protocol Specification (MPPS)**

Version 1.1.2

## **1. Abstract**

The Meta-Prompting Protocol Specification (MPPS) defines a framework for the on-the-fly generation of self-describing, task-specific communication protocols for AI interactions. It moves beyond a single, static protocol by establishing a set of rules that an intelligent agent (the "Protocol Architect") must follow to create a new, bespoke "Derivative Protocol."

The core principle of MPPS is that every message bundle must be fully self-contained, transmitting both the dynamically generated Derivative Protocol Specification (the rules) and the encoded Payload (the data). This ensures that the receiving agent (the "Executor") requires no prior knowledge of the specific protocol being used, thus achieving true model and session agnosticism. MPPS provides a blueprint for transforming prompt engineering into a more robust discipline of prompt architecture.

## **2. Core Philosophy**

The fundamental goal of MPPS is to enable a more sophisticated and reliable form of AI communication by treating each complex interaction as an opportunity to architect a perfect, purpose-built communication language.

* **From Static to Dynamic:** Instead of relying on a single, universal protocol, MPPS allows for the creation of infinite protocols, each optimized for a specific task domain (e.g., creative writing, data analysis, code generation).  
* **Self-Description as a Core Tenet:** By bundling the protocol specification with the payload, the message becomes fully self-describing. This eliminates ambiguity and the need for the receiver to have pre-trained knowledge of a specific communication schema.  
* **Model & Session Agnosticism:** Since every bundle contains the "instruction manual" on how to interpret it, any compliant Executor model can process any MPPS-compliant bundle in any session, without prior context.

## **3. Roles and Information Flow**

MPPS defines a two-stage, multi-agent workflow.

1. The Protocol Architect: An initial AI agent that receives a user's high-level goal. Guided by the MPPS rules, its primary responsibilities are:  
   - a. To analyze the goal and determine the optimal communication structure required.  
   - b. To generate a new, bespoke Derivative Protocol Specification that is perfectly suited for the task.  
   - c. To encode the user's goal into a payload according to the new specification.  
   - d. To assemble and transmit the complete MPPS Bundle.  
2. The Executor: A second AI agent (which can be a different model or the same model in a new session) that receives the MPPS Bundle. Its responsibilities are:  
   - a. To first parse the derivative_protocol_specification to learn the rules, tags, processors, and structure of the incoming message.  
   - b. To then parse the derivative_protocol_payload according to these just-in-time rules.  
   - c. To execute the task with the high degree of clarity and precision provided by the structured information.  
   - d. To return the final response.

[Optionally] The Quality Assurance Agent: A third AI agent that can be introduced to validate the Executor's output against the original user's intent, using the structured data provided in the MPPS Bundle.

## **4. MPPS Bundle Structure**

An MPPS-compliant bundle MUST be a JSON object containing the following three top-level keys:

* meta_protocol_version (String, Required): The version of the MPPS specification being followed (e.g., "1.0.0").  
* derivative_protocol_specification (Object, Required): The complete, dynamically generated specification for the Derivative Protocol.  
* derivative_protocol_payload (Object, Required): The user's request, encoded according to the rules of the derivative_protocol_specification.
  
```json
{  
  "meta_protocol_version": "1.1.2",  
  "derivative_protocol_specification": { ... },  
  "derivative_protocol_payload": { ... }  
}
```

## **5. Mandatory Components of a Derivative Specification**

To be MPPS-compliant, the derivative_protocol_specification object MUST contain the following components:

* **`protocol_name`** (String): A unique name for the generated protocol (e.g., "Structured Prompt Protocol", "Creative Writing Protocol").  
* **`abstract`** (String): A brief summary of what this protocol is designed to do.  
* **`bundle_structure`** (Object): A definition of the keys used for the payload (e.g., { "protocol_key": "cwp_protocol", "payload_key": "cwp_payload" }).  
* **`tag_definition_schema`** (Object): A description of the required fields for defining each tag (e.g., description, processor, type).  
* **`core_tag_library`**: The dictionary of all valid tags for this protocol, defined according to the `tag_definition_schema`.
* **`processor_semantics`** (Object): A dictionary describing the expected behavior of each processor mentioned in the tag library.  
* **`guiding_principles`** (Object): Rules for how to correctly apply this protocol, including principles like minimalism and fidelity.

### **5.1. Processor Semantics**
A processor is a named function or instruction that defines the specific behavior the Executor agent must apply to the data contained within a tag. Each key in this section represents a processor, and its value describes the action it performs.

### **5.2. Advanced processor implementation: Constrained Decoding**
For Derivative Protocols that specify highly structured output formats (e.g. domain-specific languages), a compliant Executor should ideally implement **Grammar-based Constrained Decoding**. This technique ensures that the generated output is not just likely to be correct, but is *guaranteed* to be syntactically valid according to the specified format. The `formatter` processor, in this case, would be responsible for translating the format description (e.g., a JSON schema from an `$output_format` tag) into a formal grammar that directly guides the LLM's token selection during generation. This represents the most robust implementation of format enforcement.

## **6. Example Walkthrough: A Creative Writing Task**

This example demonstrates the entire MPPS flow.

**User Goal:** "Write a short horror story about a lighthouse keeper who finds a strange diary. The tone should be Lovecraftian."

### **Step 1: The Protocol Architect generates a bespoke protocol, the "Creative Writing Protocol (CWP)".**

### **Step 2: The Architect encodes the user's request into a payload according to the CWP specification**

### **Step 3: The Architect assembles the final MPPS Bundle containing both the CWP specification and the CWP encoded prompt:**

```json
{  
  "meta_protocol_version": "1.1.2",  
  "derivative_protocol_specification": {  
    "protocol_name": "Creative Writing Protocol (CWP)",  
    "abstract": "A protocol for generating creative text based on structured narrative components.",  
    "bundle_structure": {  
      "protocol_key": "cwp_protocol",  
      "payload_key": "cwp_payload"  
    },  
    "tag_definition_schema": {  
      "required_fields": ["description", "processor", "type"]  
    },  
    "core_tag_library": {  
      "$genre": { "description": "The literary genre of the story.", "processor": "theme_setter", "type": "string" },  
      "$plot_points": { "description": "An array of key events or elements that must be in the story.", "processor": "narrative_injector", "type": "array" },  
      "$style_constraint": { "description": "A stylistic or tonal constraint for the writing.", "processor": "style_guardrail", "type": "string" }  
    },  
    "processor_semantics": {  
      "theme_setter": "Establishes the overall mood and genre conventions.",  
      "narrative_injector": "Ensures the core plot elements are included in the generated text.",  
      "style_guardrail": "Applies a specific literary style or voice to the generation."  
    },  
    "guiding_principles": {  
      "minimalism": "Only include tags relevant to the creative request.",  
      "fidelity": "Do not invent plot points or characters not specified by the user."  
    }  
  },  
  "derivative_protocol_payload": {  
    "cwp_protocol": {  
      "$genre": { "description": "The literary genre of the story.", "processor": "theme_setter", "type": "string" },  
      "$plot_points": { "description": "An array of key events or elements that must be in the story.", "processor": "narrative_injector", "type": "array" },  
      "$style_constraint": { "description": "A stylistic or tonal constraint for the writing.", "processor": "style_guardrail", "type": "string" }  
    },  
    "cwp_payload": {  
      "$genre": "Horror",  
      "$plot_points": [  
        "A lone lighthouse keeper.",  
        "The discovery of an old, water-logged diary.",  
        "The diary entries describe things that shouldn't be possible."  
      ],  
      "$style_constraint": "The tone must be Lovecraftian, emphasizing cosmic dread and the unknown."  
    }  
  }  
}
```

## **7. Derivative protocol example: Structured Prompt Protocol (SPP)**

Below is a concrete, general-purpose implementation of a Derivative Protocol that is fully compliant with the MPPS. This is the **agent-readable JSON object** that a Protocol Architect would generate and place in the `derivative_protocol_specification` field of an MPPS bundle.

```json
{
   "protocol_name": "Structured Prompt Protocol (SPP)",
   "abstract": "A general-purpose protocol for analytical and instructional tasks, treating prompt engineering as a data serialization problem.",
   "bundle_structure": {
     "protocol_key": "spp_protocol",
     "payload_key": "spp_payload"
   },
   "tag_definition_schema": {
     "required_fields": ["description", "processor", "type"],
     "optional_fields": ["is_required"]
   },
   "core_tag_library": {
     "$context": { "description": "The primary data or information to be processed." },
     "$task": { "description": "The main, high-level instruction or question." },
     "$directive": { "description": "A positive behavioral constraint that must be followed." },
     "$constraint": { "description": "A negative behavioral constraint that must not be violated." },
     "$output_format": { "description": "A description of the desired output structure (e.g., a JSON schema)." },
     "$validation": { "description": "A rule for validating the generated output after it has been produced." },
     "$metadata": { "description": "Ancillary information not central to the task (e.g., user ID)." },
     "$examples": { "description": "An array of few-shot examples to guide the model's response." },
     "$reasoning_strategy": { "description": "An object defining the formal reasoning method to be used." }
   },
   "processor_semantics": {
     "core_content": "Forwards the primary data/context from the `$context` tag to the AI model for analysis.",
     "instruction_handler": "Translates the `$task` into the main imperative instruction for the AI.",
     "guardrail_pre": "A pre-generation processor that acts on `$directive` and `$constraint` tags to establish rules for the AI before it generates a response (e.g., by building a system prompt).",
     "formatter": "A pre-generation processor that uses `$output_format` data to enforce a precise output structure. State-of-the-Art Implementation: Uses Grammar-based Constrained Decoding by translating a schema into a Context-Free Grammar (CFG) to guarantee syntactically perfect output.",
     "assertion_post": "A post-generation processor that validates the AI's final output against rules in a `$validation` tag (e.g., using `json.loads()`).",
     "reasoning_handler": "A pre-generation processor that configures the Executor's problem-solving approach based on the specified strategy (e.g., `chain_of_thought`).",
     "metadata_handler": "Handles ancillary data from the `$metadata` tag for external purposes like logging, not for generation.",
     "few_shot_handler": "Formats `$examples` into a structured set of demonstrations to prime the model."
   },
   "guiding_principles": {
     "minimalism": "Only include tags that are directly pertinent to the given prompt.",
     "fidelity": "The payload should be a direct, structured representation of the source prompt's intent, not an invention of new requirements."
   }
}
```
