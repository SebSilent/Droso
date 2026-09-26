
from __future__ import annotations

ACTIONS = [
    "EMBED_SEARCH",       # 0  search token embeddings (SafeTensors Library)
    "FFN_PROBE",          # 1  probe the middle FFN layer (SafeTensors Library)
    "PROJECT_TO_VOCAB",   # 2  hidden vector -> tokens (SafeTensors Library)
    "RECALL_EPISODIC",    # 3  search episodic memory
    "RECALL_SEMANTIC",    # 4  search semantic memory
    "RECALL_PROCEDURAL",  # 5  search procedural memory
    "EXECUTE_TERMINAL",   # 6  run a shell command (Terminal Organ)
    "READ_FILE",          # 7  read a file (Filesystem Organ)
    "WRITE_FILE",         # 8  write a file (Filesystem Organ)
    "ASK_USER",           # 9  prompt the human (UserInterface Organ)
    "STORE_MEMORY",       # 10 write the observation to semantic memory
    "SUBMIT_ANSWER",      # 11 declare the task complete, submit the result
]
ACTION_INDEX = {name: i for i, name in enumerate(ACTIONS)}
N_ACTIONS = len(ACTIONS)
SUBMIT_ANSWER = ACTION_INDEX["SUBMIT_ANSWER"]

LIBRARY_ACTIONS = frozenset({ACTION_INDEX["EMBED_SEARCH"],
                             ACTION_INDEX["FFN_PROBE"],
                             ACTION_INDEX["PROJECT_TO_VOCAB"]})
MEMORY_ACTIONS = frozenset({ACTION_INDEX["RECALL_EPISODIC"],
                            ACTION_INDEX["RECALL_SEMANTIC"],
                            ACTION_INDEX["RECALL_PROCEDURAL"]})

ACTION_COLORS = {
    "EMBED_SEARCH": "#60a5fa", "FFN_PROBE": "#60a5fa",
    "PROJECT_TO_VOCAB": "#60a5fa",
    "RECALL_EPISODIC": "#34d399", "RECALL_SEMANTIC": "#34d399",
    "RECALL_PROCEDURAL": "#34d399",
    "EXECUTE_TERMINAL": "#fbbf24", "READ_FILE": "#fbbf24",
    "WRITE_FILE": "#fbbf24", "ASK_USER": "#fbbf24",
    "STORE_MEMORY": "#34d399",
    "SUBMIT_ANSWER": "#4ade80",
}

def action_color(name: str) -> str:
    return ACTION_COLORS.get(name, "#94a3b8")

ACTIONS_V2 = [
    "EMBED_SEARCH",        # 0  EmbeddingAtlas nearest-neighbour
    "RELATION_TRAVERSE",   # 1  AttentionRelationGraph hop
    "FFN_PROBE",           # 2  FFNMemoryIndex slot activation
    "MICRO_CIRCUIT_RUN",   # 3  bounded micro-thought op sequence
    "RECALL_PROCEDURE",    # 4  run a compiled verified DAG
    "RECALL_SEMANTIC",     # 5  semantic memory search
    "EXECUTE_TERMINAL",    # 6  allowlisted shell
    "READ_FILE",           # 7  sandboxed file read
    "WRITE_FILE",          # 8  sandboxed file write
    "ASK_USER",            # 9  only when uncertainty is high
    "STORE_PROCEDURE",     # 10 compile the successful trace into a DAG
    "SUBMIT_RESULT",       # 11 verified submission
]
ACTION_INDEX_V2 = {name: i for i, name in enumerate(ACTIONS_V2)}
SUBMIT_RESULT = ACTION_INDEX_V2["SUBMIT_RESULT"]
LIBRARY_ACTIONS_V2 = frozenset({0, 1, 2, 3})

ACTION_COLORS_V2 = {
    "EMBED_SEARCH": "#60a5fa", "RELATION_TRAVERSE": "#60a5fa",
    "FFN_PROBE": "#60a5fa", "MICRO_CIRCUIT_RUN": "#60a5fa",
    "RECALL_PROCEDURE": "#34d399", "RECALL_SEMANTIC": "#34d399",
    "STORE_PROCEDURE": "#34d399",
    "EXECUTE_TERMINAL": "#fbbf24", "READ_FILE": "#fbbf24",
    "WRITE_FILE": "#fbbf24", "ASK_USER": "#fbbf24",
    "SUBMIT_RESULT": "#4ade80",
}

ACTIONS_V3 = [
    "EMBED_SEARCH",        # 0  EmbeddingAtlas nearest-neighbour
    "RELATION_TRAVERSE",   # 1  AttentionRelationGraph hop
    "FFN_PROBE",           # 2  FFNMemoryIndex slot activation
    "MICRO_CIRCUIT_RUN",   # 3  bounded micro-thought op sequence
    "RECALL_PROCEDURE",    # 4  run a compiled verified DAG
    "RECALL_SEMANTIC",     # 5  semantic memory search
    "EXECUTE_TERMINAL",    # 6  allowlisted shell
    "READ_FILE",           # 7  sandboxed file read
    "WRITE_FILE",          # 8  sandboxed file write
    "ASK_USER",            # 9  only when uncertainty is high
    "STORE_PROCEDURE",     # 10 compile the successful trace into a DAG
    "SUBMIT_RESULT",       # 11 verified submission
    "RETRIEVE_SNIPPET",    # 12 pull a base AST from the snippet vault
    "MUTATE_CODE",         # 13 structural AST mutation of the working snippet
    "VERIFY_CODE",         # 14 py_compile / ast.parse on the assembled code
]
ACTION_INDEX_V3 = {name: i for i, name in enumerate(ACTIONS_V3)}
SUBMIT_RESULT_V3 = ACTION_INDEX_V3["SUBMIT_RESULT"]
LIBRARY_ACTIONS_V3 = frozenset({0, 1, 2, 3})
CODE_ACTIONS_V3 = frozenset({12, 13, 14})

ACTION_COLORS_V3 = {**ACTION_COLORS_V2,
                    "RETRIEVE_SNIPPET": "#f472b6", "MUTATE_CODE": "#f472b6",
                    "VERIFY_CODE": "#fb7185"}

ACTIONS_V4 = ACTIONS_V3 + [
    "ANALYZE_TASK",        # 15 classify task type + domain -> st.analysis
    "SELECT_LAYERS",       # 16 layer router (analyzer prior + learned prefs)
    "SPARSE_INFERENCE",    # 17 run ONLY the selected layers
    "DECODE_OUTPUT",       # 18 hidden state -> tokens/fragments/memory
]
ACTION_INDEX_V4 = {name: i for i, name in enumerate(ACTIONS_V4)}
SUBMIT_RESULT_V4 = ACTION_INDEX_V4["SUBMIT_RESULT"]
LIBRARY_ACTIONS_V4 = frozenset({0, 1, 2, 3})
CODE_ACTIONS_V4 = frozenset({12, 13, 14})
LAYER_ACTIONS_V4 = frozenset({15, 16, 17, 18})

ACTION_COLORS_V4 = {**ACTION_COLORS_V3,
                    "ANALYZE_TASK": "#38bdf8", "SELECT_LAYERS": "#818cf8",
                    "SPARSE_INFERENCE": "#a78bfa", "DECODE_OUTPUT": "#34d399"}

ACTIONS_V5 = ACTIONS_V4 + [
    "STORE_WORKING_MEMORY",   # 19 hold a thought in mind
    "RETRIEVE_WORKING_MEMORY",  # 20 recall what is being held
    "GENERATE_HYPOTHESES",    # 21 ask the hypothesis organ for approaches
    "EVALUATE_APPROACH",      # 22 score / rank an approach
    "CREATE_PLAN",            # 23 break the goal into verifiable steps
    "EXECUTE_STEP",           # 24 run the next plan step through the body
    "CHECK_RESULT",           # 25 verify a step's outcome
    "BACKTRACK",              # 26 abandon approach, fall to the next
    "TRACE_CAUSALITY",        # 27 dependencies / effects / root cause
    "REQUEST_LLM_HELP",       # 28 query the LLM tool for specific knowledge
]
ACTION_INDEX_V5 = {name: i for i, name in enumerate(ACTIONS_V5)}
N_ACTIONS_V5 = len(ACTIONS_V5)
REASONING_ACTIONS_V5 = frozenset(range(19, 29))

ACTION_COLORS_V5 = {**ACTION_COLORS_V4,
                    "STORE_WORKING_MEMORY": "#fbbf24",
                    "RETRIEVE_WORKING_MEMORY": "#fcd34d",
                    "GENERATE_HYPOTHESES": "#f472b6",
                    "EVALUATE_APPROACH": "#fb923c",
                    "CREATE_PLAN": "#22d3ee",
                    "EXECUTE_STEP": "#4ade80",
                    "CHECK_RESULT": "#a3e635",
                    "BACKTRACK": "#ef4444",
                    "TRACE_CAUSALITY": "#c084fc",
                    "REQUEST_LLM_HELP": "#60a5fa"}