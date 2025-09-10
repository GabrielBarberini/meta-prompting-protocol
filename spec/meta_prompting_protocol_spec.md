# **Meta-Prompting Protocol Specification (MPPS)**

Version 1.1.1

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
   a. To analyze the goal and determine the optimal communication structure required.  
   b. To generate a new, bespoke Derivative Protocol Specification that is perfectly suited for the task.  
   c. To encode the user's goal into a payload according to the new specification.  
   d. To assemble and transmit the complete MPPS Bundle.  
2. The Executor: A second AI agent (which can be a different model or the same model in a new session) that receives the MPPS Bundle. Its responsibilities are:  
   a. To first parse the derivative_protocol_specification to learn the rules, tags, processors, and structure of the incoming message.  
   b. To then parse the derivative_protocol_payload according to these just-in-time rules.  
   c. To execute the task with the high degree of clarity and precision provided by the structured information.  
   d. To return the final response.

## **4. MPPS Bundle Structure**

An MPPS-compliant bundle MUST be a JSON object containing the following three top-level keys:

* meta_protocol_version (String, Required): The version of the MPPS specification being followed (e.g., "1.0.0").  
* derivative_protocol_specification (Object, Required): The complete, dynamically generated specification for the Derivative Protocol.  
* derivative_protocol_payload (Object, Required): The user's request, encoded according to the rules of the derivative_protocol_specification.
  
```json
{  
  "meta_protocol_version": "1.0.0",  
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
* **`core_tag_library`** (Object): The dictionary of all valid tags for this protocol, defined according to the tag_definition_schema.  
* **`processor_semantics`** (Object): A dictionary describing the expected behavior of each processor mentioned in the tag library.  
* **`guiding_principles`** (Object): Rules for how to correctly apply this protocol, including principles like minimalism and fidelity.
* **`core_tag_library`**: The dictionary of all valid tags for this protocol, defined according to the `tag_definition_schema`.
 * **`processor_semantics`** (Object): A dictionary describing the expected behavior of each processor mentioned in the tag library.
 * **`guiding_principles`** (Object): Rules for how to correctly apply this protocol, including principles like minimalism and fidelity.

### 5.1. Advanced Processor Implementation Note: Constrained Decoding
For Derivative Protocols that specify highly structured output formats (e.g., JSON, XML, or domain-specific languages), a compliant Executor should ideally implement **Grammar-based Constrained Decoding**. This technique ensures that the generated output is not just likely to be correct, but is *guaranteed* to be syntactically valid according to the specified format. The `formatter` processor, in this case, would be responsible for translating the format description (e.g., a JSON schema from an `$output_format` tag) into a formal grammar that directly guides the LLM's token selection during generation. This represents the most robust implementation of format enforcement.


## **6. Example Walkthrough: A Creative Writing Task**

This example demonstrates the entire MPPS flow.

**User Goal:** "Write a short horror story about a lighthouse keeper who finds a strange diary. The tone should be Lovecraftian."

### **Step 1 & 2: The Protocol Architect generates a bespoke protocol, the "Creative Writing Protocol (CWP) v1.0".**

### **Step 3: The Architect assembles the final MPPS Bundle:**

```json
{  
  "meta_protocol_version": "1.0.0",  
  "derivative_protocol_specification": {  
    "protocol_name": "Creative Writing Protocol (CWP)",  
    "protocol_version": "1.0",  
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

Below is a concrete, general-purpose implementation example of a Derivative Protocol that is fully compliant with the MPPS. Its robust set of tags ($context, $task, $constraint, etc.) makes it a powerful default choice for a wide variety of technical and analytical tasks.

### **Structured Prompt Protocol (SPP) Specification**
**Version: 1.1.0**

#### **Preamble: MPPS Compliance**

This document specifies the **Structured Prompt Protocol (SPP)**, a general-purpose Derivative Protocol for analytical and instructional tasks. It is designed to be fully compliant with the **Meta-Prompting Protocol Specification (MPPS) v1.0.0**.

As a compliant Derivative Protocol, this entire specification serves as a concrete example of what a "Protocol Architect" agent would generate on the fly and include in the `derivative_protocol_specification` field of an MPPS bundle.

#### **1. Abstract**

The Structured Prompt Protocol (SPP) provides a formal architecture for encoding user intentions, data, constraints, and processing instructions into a single, structured message bundle. It is designed to overcome the ambiguity of "flat" text prompts by segregating information into tagged logical blocks, each of which can be mapped to a specific processor on the receiving end. This enables highly reliable, controllable, and extensible interactions with language models and other AI systems. SPP treats prompt engineering as a data serialization problem, not just a linguistic one.

#### **2. Core Concepts**

* **Tag:** A unique identifier for a piece of data within the prompt. Tags are denoted by a string, with a `$` prefix conventionally used for core, reserved tags.  
* **Protocol:** A schema that defines the set of valid Tags for a given interaction. It specifies each Tag's purpose, data type, and the suggested processor for handling its data.  
* **Payload:** An instance of the Protocol, containing the actual data for each Tag.  
* **Processor:** A functional module on the receiver side responsible for interpreting and acting upon the data from a specific Tag (e.g., a guardrail enforcer, a code validator, a data formatter). The Protocol only *suggests* a processor; the receiver implements it.  
* **Bundle:** The complete message transmitted, containing both the Protocol and the Payload, along with versioning information.

#### **3. Architecture and Data Flow**

This protocol defines a two-sided interaction model: a Transmitter that composes and sends the Bundle, and a Receiver that parses and processes it.

**Transmitter Side:**

1. **User Input:** Receives the user's raw request.  
2. **Protocol Formulation:** Dynamically generates a Protocol defining the necessary Tags ($context, $task, $constraint, etc.) for the request.  
3. **Payload Encoding:** Populates the Payload by parsing the user input and assigning it to the appropriate Tags.  
4. **Bundle Creation & Transmission:** Assembles the Protocol and Payload into a single SPP Bundle and transmits it within an MPPS-compliant wrapper if required.

**Receiver Side:**

1. **Bundle Reception:** Receives the SPP Bundle.  
2. **Protocol Processing:** Parses the `spp_protocol` section to understand the structure, tags, and processor hints for the incoming message.  
3. **Payload Decoding:** Iterates through the `spp_payload`, routing the data for each Tag to the corresponding Processor suggested by the Protocol.  
4. **Enriched Processing:** The Processors collectively assemble an enriched, highly specific set of instructions and data for the core AI model (e.g., LLM).  
5. **Generation & Validation:** The AI model generates a response. Post-generation Processors (e.g., for `$validation` tags) check the output for compliance.  
6. **Final Response:** The validated, compliant response is sent back to the user.

#### **4. Guiding Principles for Dynamic Formulation**

To ensure SPP Bundles are efficient and accurately reflect the user's intent, implementers (both human and AI) must adhere to the following principles when formulating the protocol and encoding the payload. This prevents the common pitfall of including all possible tags from the standard library regardless of their relevance.

##### 4.1. The Principle of Minimalism (Contextual Relevance)
Only include tags that are directly pertinent to the given prompt. The protocol for a given prompt should be as lean as possible. If a prompt component (like external context or a validation rule) does not exist, its corresponding tag MUST NOT be included in the bundle.

##### 4.2. The Principle of Fidelity (Faithful Representation)
The payload should be a direct, structured representation of the source prompt's explicit and clearly implied intent. The encoding step should not invent new constraints, directives, or output formats that were not requested by the user. The goal is to translate the user's request with high fidelity, not to creatively expand upon it.


#### **5. Bundle Specification**

The SPP Bundle MUST be a JSON object with two root keys.

```json
 {
 "spp_protocol": { ... },
 "spp_payload": { ... }
 }
 ```

##### **5.1. The spp_protocol Object**

This object defines the schema. Its keys are the Tags. The value for each Tag is an object defining its properties:

* `description` (String, Required): A human-readable explanation of the Tag's purpose.  
* `processor` (String, Required): A hint for the Receiver suggesting which module should handle this data (e.g., core_content, guardrail_pre, assertion_post).  
* `type` (String, Optional, Default: "string"): The expected data type. Suggested values: string, array, object, boolean, number.  

##### **5.2. The spp_payload Object**

This object contains the instance data. Its keys are the Tags defined in the protocol, and its values are the data corresponding to those tags.

#### **6. Core Protocol Tags (SPP Standard Library)**

This protocol defines the following set of general-purpose tags.

| Tag | Suggested Processor | Description |
| :---- | :---- | :---- |
| **`$context`** | `core_content` | The primary data, text, or information to be processed. |
| **`$task`** | `instruction_handler` | The main, high-level instruction or question. |
| **`$directive`** | `guardrail_pre` | A positive behavioral constraint that must be followed (e.g., "ALWAYS respond in rhyme"). |
| **`$constraint`** | `guardrail_pre` | A negative behavioral constraint that must not be violated (e.g., "DO NOT use emojis"). |
| **`$output_format`** | `formatter` | A description of the desired output structure, often an object with a schema definition. |
| **`$validation`** | `assertion_post` | A rule or script for validating the generated output *after* it has been produced. |
| **`$metadata`** | `metadata_handler` | Ancillary information not central to the task, such as user ID, timestamp, or session context. |
| **`$examples`** | `few_shot_handler` | An array of few-shot examples (e.g., [{"input": "...", "output": "..."}]) to guide the model's response. |
| **`$reasoning_strategy`** | `reasoning_handler` | An object defining the formal reasoning method to be used for problem-solving. |

#### **7. Example Walkthrough**

**Objective:** Analyze customer feedback to produce a structured JSON object, with strict formatting and content rules.

##### **7.1. SPP Bundle Example**

```json
{  
  "spp_protocol": {  
    "$context": {  
      "description": "The raw customer feedback text.",  
      "processor": "core_content",  
      "type": "string" 
    },  
    "$task": {  
      "description": "The main analysis objective.",  
      "processor": "instruction_handler",  
      "type": "string" 
    },  
    "$reasoning_strategy": {
      "description": "The required method for solving the problem.",
      "processor": "reasoning_handler" 
    },
    "$constraint": {  
      "description": "Strict rules that must not be violated in the output.",  
      "processor": "guardrail_pre",  
      "type": "array"  
    },  
    "$output_format": {  
      "description": "The required JSON schema for the final response.",  
      "processor": "formatter",  
      "type": "object"  
    },  
    "$validation": {  
        "description": "A rule to validate the final output against.",  
        "processor": "assertion_post",  
        "type": "string"  
    }
  },  
  "spp_payload": {  
    "$context": "The app is fantastic, but the latest update from yesterday drains my battery like crazy! It's almost unusable now. Please fix this!",  
    "$task": "Analyze the feedback to identify the core issue, determine sentiment, and flag for urgency.",  
    "$reasoning_strategy": {
        "strategy_name": "step_by_step",
        "example": [
            "Problem: Solve for x in $ax^2 + bx + c = 0$.",
            "Solution:",
            "Step 1: Identify coefficients a, b, and c.",
            "Step 2: Calculate the discriminant: $\\Delta = b^2 - 4ac$.",
            "Step 3: Apply the quadratic formula: $x = \\frac{-b \\pm \\sqrt{\\Delta}}{2a}$.",
            "Step 4: Simplify to find the roots."
        ]
    },
    "$constraint": [  
      "Do not add any conversational filler or apologies.",  
      "Do not include any fields in the JSON other than those specified."  
    ],  
    "$output_format": {  
      "format": "json",  
      "schema": {  
        "summary": "string",  
        "sentiment": "string (enum: 'positive', 'negative', 'mixed')",  
        "is_urgent": "boolean"  
      }  
    },  
    "$validation": "The output must be a valid JSON object." 
  }  
}
```

##### **7.2. Expected Final Response (Post-Processing)**
```json
{  
  "summary": "User reports severe battery drain after the most recent app update.",  
  "sentiment": "mixed",  
  "is_urgent": true  
}
```

#### **8. Processor Semantics**
This section describes the expected behavior of the standard processors.

* `core_content`: Forwards the primary data/context from the $context tag to the AI model for analysis.
* `instruction_handler`: Translates the $task into the main imperative instruction for the AI.
* `guardrail_pre`: A pre-generation processor that acts on $directive and $constraint tags to establish rules for the AI before it generates a response. Implementation Example: Dynamically constructing a system prompt or setting API parameters for content filtering.
* `formatter`: A pre-generation processor that uses the $output_format data to enforce a precise output structure. State-of-the-Art Implementation Example: For maximum reliability, this processor translates the schema from the $output_format tag into a formal Context-Free Grammar (CFG). It then uses Grammar-based Constrained Decoding to force the Executor LLM to generate a syntactically perfect output, token by token. This moves from simply requesting a format to guaranteeing it.
* `assertion_post`: A post-generation processor that validates the AI's final output against rules in a $validation tag. Implementation Example: Using Python code to run json.loads() on the output to assert it's valid JSON.
* `reasoning_handler`: A pre-generation processor that configures the Executor's problem-solving approach. It interprets the specified strategy (e.g., chain_of_thought, tree_of_thought) and primes the model to follow that structure, often by dynamically generating a meta-prompt that enforces the chosen methodology.
* `metadata_handler`: Handles ancillary data from the $metadata tag for external purposes like logging, not for generation.
* `few_shot_handler`: Formats $examples into a structured set of demonstrations to prime the model.
