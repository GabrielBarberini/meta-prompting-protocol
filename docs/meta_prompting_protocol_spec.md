# **Meta-Prompting Protocol Specification (MPP)**

Version 1.1.5

## **1. Abstract**

The Meta-Prompting Protocol Specification (MPP) defines a framework for the on-the-fly generation of self-describing, task-specific communication protocols for AI interactions. It moves beyond a single, static protocol by establishing a set of rules that an intelligent agent (the "Protocol Architect") must follow to create a new, bespoke "Derivative Protocol."

The core principle of MPP is that every message bundle must be fully self-contained, transmitting both the dynamically generated Derivative Protocol Specification (the rules) and the encoded Payload (the data). This ensures that the receiving agent (the "Executor") requires no prior knowledge of the specific protocol being used, thus achieving true model and session agnosticism. MPP provides a blueprint for transforming prompt engineering into a more robust discipline of prompt architecture.

## **2. Core Philosophy**

The fundamental goal of MPP is to enable a more sophisticated and reliable form of AI communication by treating each complex interaction as an opportunity to architect a perfect, purpose-built communication language.

* **From Static to Dynamic:** Instead of relying on a single, universal protocol, MPP allows for the creation of infinite protocols, each optimized for a specific task domain (e.g., creative writing, data analysis, code generation).  
* **Self-Description as a Core Tenet:** By bundling the protocol specification with the payload, the message becomes fully self-describing. This eliminates ambiguity and the need for the receiver to have pre-trained knowledge of a specific communication schema.  
* **Model & Session Agnosticism:** Since every bundle contains the "instruction manual" on how to interpret it, any compliant Executor model can process any MPP-compliant bundle in any session, without prior context.

## **3. Roles and Information Flow**

MPP defines a two-stage, multi-agent workflow.

1. The Protocol Architect: An initial AI agent that receives a user's high-level goal. Guided by the MPP rules, its primary responsibilities are:  
   - a. To analyze the goal and determine the optimal communication structure required.  
   - b. To generate a new, bespoke Derivative Protocol Specification that is perfectly suited for the task.  
   - c. To encode the user's goal into a payload according to the new specification.  
   - d. To assemble and transmit the complete MPP Bundle.  
   - e. To iteratively polish the protocol and payload via a refine -> validate -> revise loop until stable (monadic refinement).  
2. The Executor: A second AI agent (which can be a different model or the same model in a new session) that receives the MPP Bundle. Its responsibilities are:  
   - a. To first parse the derivative_protocol_specification to learn the rules, tags, processors, and structure of the incoming message.  
   - b. To then parse the derivative_protocol_payload according to these just-in-time rules.  
   - c. To execute the task with the high degree of clarity and precision provided by the structured information.  
   - d. To return the final response.  
   - e. To iteratively decode, validate, and polish the response until stable against the protocol constraints (monadic refinement).  

[Optionally] The Quality Assurance Agent: A third AI agent that can be introduced to validate the Executor's output against the original user's intent, using the structured data provided in the MPP Bundle.

## **3.1 Iterative Polishing (Monadic Refinement)**

MPP assumes that both protocol derivation (input layer) and protocol decoding (output layer) benefit from iterative polishing. A Protocol Architect SHOULD run a refine -> validate -> revise loop until the derived specification and payload stop changing materially. An Executor SHOULD apply the same loop during decoding, re-generating and re-validating until the output consistently satisfies the protocol's constraints.

## **4. MPP Bundle Structure**

An MPP-compliant bundle MUST be a JSON object containing the following three top-level keys:

* `meta_protocol_version` (String, Required): The version of the MPP specification being followed (e.g., "1.0.0").  
* `derivative_protocol_specification` (Object, Required): The complete, dynamically generated specification for the Derivative Protocol.  
* `derivative_protocol_payload` (Object, Required): The user's request, encoded according to the rules of the derivative_protocol_specification.
  
```json
{  
  "meta_protocol_version": "1.1.5",  
  "derivative_protocol_specification": { ... },  
  "derivative_protocol_payload": { ... }  
}
```

## **4.1 Ordering and Attention Guidance**

MPP bundles are typically serialized into a single prompt. To reduce attention
confusion, definitions SHOULD appear before references. When serializing
derivative_protocol_specification, use definition-first ordering: protocol_name,
protocol_version (if any), abstract, guiding_principles, tag_definition_schema,
processor_semantics, core_tag_library, then any optional ordered metadata
(e.g., payload_order, processor_pipeline).

JSON objects are unordered. If payload ordering matters, the derivative protocol
SHOULD declare it explicitly (see 5.2).

## **5. Mandatory Components of a Derivative Specification**

To be MPP-compliant, the derivative_protocol_specification object MUST contain the following components:

* **`protocol_name`** (String): A unique name for the generated protocol (e.g., "Structured Prompt Protocol", "Creative Writing Protocol"). 
* **`abstract`** (String): A brief summary of what this protocol is designed to do.  
* **`guiding_principles`** (Object): Rules for how to correctly apply this protocol, including principles like minimalism and fidelity.
* **`tag_definition_schema`** (Schema Descriptor, Array of Strings): An ordered list of required fields for defining each tag (e.g., description, processor, type). Tag definitions MAY include additional optional fields beyond this schema.  
* **`processor_semantics`** (Object): A dictionary describing the expected behavior of each processor mentioned in the tag library.  
* **`core_tag_library`**: The dictionary of all valid tags for this protocol, defined according to the `tag_definition_schema`.

No additional top-level keys are allowed beyond the mandatory components and the
optional ordered metadata defined in 5.2.

### **5.1. Processor Semantics**
A processor is a named function or instruction that defines the specific behavior the Executor agent must apply to the data contained within a tag. Each key in this section represents a processor, and its value describes the action it performs.

### **5.2. Optional Ordered Metadata**
Derivative Protocols MAY include ordered metadata when sequence matters:

* **`protocol_version`** (String, Optional): A version identifier for the derivative protocol.
* **`payload_order`** (Array of Strings, Optional): Ordered list of payload tag keys.
  Executors SHOULD process payload tags in this order when present. The payload
  MUST contain exactly these tags and preserve this order.
* **`processor_pipeline`** (Array of Strings, Optional): Ordered list of processor
  names. Executors SHOULD apply processors in this sequence when multiple
  processors are involved. When present, it requires payload_order and MUST
  match the processor order implied by payload_order.

Values in `payload_order` MUST reference keys in `core_tag_library`. Values in
`processor_pipeline` MUST reference processors defined in `processor_semantics`.

### **5.3. Tag Optionality**
Each tag definition MAY include a **`required`** boolean (default: true). Tags
omitted from the payload are only allowed when their definition explicitly sets
`required: false`.

## **6. Example Walkthrough: A Creative Writing Task**

This example demonstrates the entire MPP flow.

**User Goal:** "Write a short horror story about a lighthouse keeper who finds a strange diary. The tone should be Lovecraftian."

- **Step 1: The Protocol Architect generates a bespoke protocol, the "Creative Writing Protocol (CWP)";**

- **Step 2: The Architect encodes the user's request into a payload according to the CWP specification;**

- **Step 3: The Architect assembles the final MPP Bundle containing both the CWP specification and the CWP encoded prompt:**

```json
{  
  "meta_protocol_version": "1.1.5",  
  "derivative_protocol_specification": {  
    "protocol_name": "Creative Writing Protocol (CWP)",  
    "protocol_version": "1.0",
    "abstract": "A protocol for generating creative text based on structured narrative components.", 
    "guiding_principles": {  
      "minimalism": "Only include tags relevant to the creative request.",  
      "fidelity": "Do not invent plot points or characters not specified by the user."  
    },
    "tag_definition_schema": ["description", "processor", "type"],
    "processor_semantics": {  
      "theme_setter": "Establishes the overall mood and genre conventions.",  
      "narrative_injector": "Ensures the core plot elements are included in the generated text.",  
      "style_guardrail": "Applies a specific literary style or voice to the generation."  
    },  
    "core_tag_library": {  
      "$genre": { "description": "The literary genre of the story.", "processor": "theme_setter", "type": "string" },  
      "$plot_points": { "description": "An array of key events or elements that must be in the story.", "processor": "narrative_injector", "type": "array" },  
      "$style_constraint": { "description": "A stylistic or tonal constraint for the writing.", "processor": "style_guardrail", "type": "string" }  
    },
    "payload_order": [
      "$genre",
      "$plot_points",
      "$style_constraint"
    ],
    "processor_pipeline": [
      "theme_setter",
      "narrative_injector",
      "style_guardrail"
    ]
  },  
  "derivative_protocol_payload": {  
    "$genre": "Horror",  
    "$plot_points": [  
      "A lone lighthouse keeper.",  
      "The discovery of an old, water-logged diary.",  
      "The diary entries describe things that shouldn't be possible."  
    ],  
    "$style_constraint": "The tone must be Lovecraftian, emphasizing cosmic dread and the unknown."  
  }  
} 
```

## **6.1 Another derivative protocol example: Structured Prompt Protocol (SPP)**

```json
{
  "protocol_name": "Structured Prompt Protocol (SPP)",
  "protocol_version": "1.0",
  "abstract": "A general-purpose protocol for analytical and instructional tasks, treating prompt engineering as a data serialization problem.",
  "guiding_principles": {
    "minimalism": "Only include tags that are directly pertinent to the given prompt.",
    "fidelity": "The payload should be a direct, structured representation of the source prompt's intent, not an invention of new requirements."
  },
  "tag_definition_schema": ["description", "processor", "type"],
  "processor_semantics": {
    "core_content": "Forwards the primary data/context from the `$context` tag to the AI model for analysis.",
    "instruction_handler": "Translates the `$task` into the main imperative instruction for the AI.",
    "guardrail_pre": "A pre-generation processor that acts on `$directive` and `$constraint` tags to establish rules for the AI before it generates a response (e.g., by building a system prompt).",
    "formatter": "A pre-generation processor that uses `$output_format` data to enforce a precise output structure and validate conformance.",
    "assertion_post": "A post-generation processor that validates the AI's final output against rules in a `$validation` tag (e.g., using `json.loads()`).",
    "reasoning_handler": "A pre-generation processor that configures the Executor's problem-solving approach based on the specified strategy (e.g., `chain_of_thought`).",
    "metadata_handler": "Handles ancillary data from the `$metadata` tag for external purposes like logging, not for generation.",
    "few_shot_handler": "Formats `$examples` into a structured set of demonstrations to prime the model."
  },
  "core_tag_library": {
    "$context": {
      "description": "The primary data or information to be processed.",
      "processor": "core_content",
      "type": "any"
    },
    "$task": {
      "description": "The main, high-level instruction or question.",
      "processor": "instruction_handler",
      "type": "string"
    },
    "$directive": {
      "description": "A positive behavioral constraint that must be followed.",
      "processor": "guardrail_pre",
      "type": "string"
    },
    "$constraint": {
      "description": "A negative behavioral constraint that must not be violated.",
      "processor": "guardrail_pre",
      "type": "string"
    },
    "$output_format": {
      "description": "A description of the desired output structure (e.g., a JSON schema).",
      "processor": "formatter",
      "type": "object"
    },
    "$validation": {
      "description": "A rule for validating the generated output after it has been produced.",
      "processor": "assertion_post",
      "type": "object"
    },
    "$metadata": {
      "description": "Ancillary information not central to the task (e.g., user ID).",
      "processor": "metadata_handler",
      "type": "object"
    },
    "$examples": {
      "description": "An array of few-shot examples to guide the model's response.",
      "processor": "few_shot_handler",
      "type": "array"
    },
    "$reasoning_strategy": {
      "description": "An object defining the formal reasoning method to be used.",
      "processor": "reasoning_handler",
      "type": "object"
    }
  }
}
```
