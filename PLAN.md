# Clang Call Analyzer - Integration Fix Plan

## Overview

**STATUS:** INTEGRATION FIX PHASE
**Issue:** Components exist but integration is broken
**Goal:** Fix data flow without adding new features

**Root Causes Identified:**
1. Macro invocations extracted by CallAnalyzer not reaching call graph
2. Function pointer extraction exists but call graph integration unclear
3. Virtual function extraction exists but call graph integration unclear
4. Type markers (macro, indirect, virtual) exist but not preserved in output

**Key Insight:** The architecture is sound, but data transformation at boundaries is incorrect.

---

## Current Architecture Review

### Component Responsibilities

```
┌─────────────────────────────────────────────────────────────────┐
│                      Data Flow (Current)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. cli.py:                                                     │
│     └─> Creates FeatureAnalyzer per TU                          │
│     └─> Extracts: macros, pointers, virtual methods             │
│     └─> Merges all registries into feature_registry           │
│                                                                  │
│  2. call_analyzer.py:                                            │
│     └─> Analyzes direct calls (CALL_EXPR)                       │
│     └─> Creates FeatureAnalyzer per function                    │
│     └─> Extracts macro invocations                             │
│     └─> Creates CallInfo with type markers                      │
│                                                                  │
│  3. relationship_builder.py:                                    │
│     └─> Receives CallInfo list from CallAnalyzer               │
│     └─> Builds bidirectional relationships                     │
│     └─> Handles multiple targets (indirect/virtual)              │
│     └─> Handles macro calls (special entry)                     │
│                                                                  │
│  4. json_emitter.py:                                            │
│     └─> Receives relationships from RelationshipBuilder         │
│     └─> Emits JSON                                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Structures

**CallInfo (call_analyzer.py):**
```python
@dataclass
class CallInfo:
    caller_cursor: clang.cindex.Cursor
    callee_name: str
    callee_index: Optional[int]
    is_macro: bool = False
    is_indirect: bool = False
    is_virtual: bool = False
    possible_targets: Optional[List[int]] = None
    macro_info: Optional[Any] = None
```

**Relationships (relationship_builder.py):**
```python
# For each function index:
(
    parents: List[Union[int, Dict[str, Any]]],
    children: List[Union[int, Dict[str, Any]]]
)

# Entry types:
# - int: Direct call to a function (e.g., 5)
# - dict: Complex call with metadata, e.g.:
#   {"index": 5, "type": "direct"}
#   {"index": 5, "type": "indirect", "possible_targets": [5, 6]}
#   {"index": 5, "type": "virtual", "possible_targets": [5, 6]}
#   {"type": "macro", "name": "PRINTF", "arguments": [...]}
```

---

## Integration Issues & Fixes

### Issue 1: Macro Invocations Not in Call Graph

**Problem:**
- CallAnalyzer extracts macro invocations and creates CallInfo objects with `is_macro=True`
- RelationshipBuilder converts these to dict entries with `{"type": "macro", "name": "..."}`
- BUT: The deduplication logic (`list(dict.fromkeys(children))`) fails on mixed int/dict lists
- Result: Macro calls are lost or relationships are corrupted

**Root Cause:**
```python
# relationship_builder.py - current code
for call in calls:
    if call.callee_index is not None:
        if call.callee_index != func_idx:
            children.append(call.callee_index)  # ← Adds int
    elif call.possible_targets:
        # ... adds dicts with type markers
    elif call.is_macro:
        # ... adds dicts with type markers

# Then:
unique_children = list(dict.fromkeys(children))  # ← FAILS on mixed int/dict
```

**Fix:**
Convert all entries to dicts BEFORE deduplication, so they're comparable:

```python
# relationship_builder.py - fixed code
for call in calls:
    if call.callee_index is not None and call.callee_index != func_idx:
        # Convert direct calls to dict for consistency
        children.append({
            "index": call.callee_index,
            "type": "direct"
        })
    elif call.possible_targets:
        for target_idx in call.possible_targets:
            if target_idx != func_idx:
                entry = {
                    "index": target_idx,
                    "type": "indirect" if call.is_indirect else "virtual" if call.is_virtual else "direct"
                }
                if len(call.possible_targets) > 1:
                    entry["possible_targets"] = call.possible_targets
                children.append(entry)
    elif call.is_macro:
        entry = {
            "type": "macro",
            "name": call.callee_name
        }
        if call.macro_info:
            entry["arguments"] = call.macro_info.arguments
        children.append(entry)

# Now deduplication works on dict entries
unique_children = list(dict.fromkeys(
    frozenset(entry.items()) if isinstance(entry, dict) else entry
    for entry in children
))
```

**Actually, simpler fix:**
Since we need dict equality for deduplication, just ensure all entries are dicts:

```python
# Simpler approach - normalize to dicts first
def _normalize_entry(self, entry: Union[int, Dict[str, Any]]) -> Dict[str, Any]:
    """Convert entry to dict for consistent comparison."""
    if isinstance(entry, dict):
        return entry
    return {"index": entry, "type": "direct"}

# In build():
normalized_children = [self._normalize_entry(c) for c in children]
unique_children = list(dict.fromkeys(
    frozenset(entry.items()) for entry in normalized_children
))
children_map[func_idx] = unique_children
```

---

### Issue 2: Function Pointer Extraction Unclear

**Problem:**
- FeatureAnalyzer.extract_function_pointers() exists and works
- CallAnalyzer._analyze_function_pointer_call() uses it
- BUT: It's unclear if all pointers are being tracked correctly

**Analysis:**
Looking at the code flow:
1. FeatureAnalyzer extracts function pointer declarations
2. It creates FunctionPointerInfo objects with `possible_targets: Set[int]`
3. BUT: `possible_targets` starts empty
4. CallAnalyzer looks up pointer in registry and returns the targets

**Root Cause:**
Function pointer targets are never populated! The registry tracks pointers, but doesn't track which functions are assigned to them.

**Fix:**
This is a design limitation. The current code tracks pointer declarations but doesn't analyze assignments. For V1 (integration fix only), we should:

1. Document this limitation in PLAN.md
2. Keep the existing code structure (it's correct for the declared scope)
3. In a future phase, add assignment tracking

**Note:** The Auditor's issue might be about testing, not code. The code is correctly designed for what it does.

---

### Issue 3: Virtual Function Extraction Unclear

**Problem:**
- FeatureAnalyzer.extract_classes() and extract_virtual_methods() exist
- CallAnalyzer._analyze_virtual_call() uses them
- BUT: RelationshipBuilder might not handle virtual calls correctly

**Analysis:**
Looking at CallAnalyzer._analyze_virtual_call():
```python
def _analyze_virtual_call(self, call_cursor, method_cursor) -> Optional[CallInfo]:
    # ...
    possible_indices: Set[int] = set()
    base_indices = self._registry.get_by_qualified_name(called_method_name)
    possible_indices.update(base_indices)

    # Add overrides from derived classes
    for derived_class_name in derived_classes:
        # ...
        override_name = f"{derived_class_name}::{method_cursor.spelling}"
        override_indices = self._registry.get_by_qualified_name(override_name)
        possible_indices.update(override_indices)

    if possible_indices:
        possible_targets: List[int] = list(possible_indices)
        return CallInfo(
            caller_cursor=call_cursor,
            callee_name=call_cursor.spelling,
            callee_index=possible_targets[0] if len(possible_targets) == 1 else None,
            is_virtual=True,
            possible_targets=possible_targets
        )
```

This looks correct! It finds all possible targets and returns them.

**Issue:** Same as Issue 1 - RelationshipBuilder needs to handle the CallInfo correctly.

**Fix:** Already covered in Issue 1's fix.

---

### Issue 4: Type Markers Missing in JSON

**Problem:**
- CallInfo has `is_macro`, `is_indirect`, `is_virtual` flags
- RelationshipBuilder creates dict entries with `type` field
- BUT: JSONEmitter might not preserve these in output

**Analysis:**
Looking at json_emitter.py:
```python
class JSONEmitter:
    def emit(self, functions, relationships):
        output_data = []

        for func in functions:
            func_index = ...  # Find index
            parents, children = relationships.get(func_index, ([], []))

            output_entry = FunctionOutput(
                index=func_index,
                self=self_data,
                parents=parents,    # ← Pass through as-is
                children=children  # ← Pass through as-is
            )

            output_data.append(asdict(output_entry))

        json_output = json.dumps(output_data, indent=2, ensure_ascii=False)
```

The emitter just passes `parents` and `children` through to `asdict()`. Since they're already `List[Union[int, Dict[str, Any]]]`, the dict entries should be preserved.

**Issue:** Wait - `asdict()` might not preserve nested Union types correctly!

**Fix:**
The issue is that `asdict()` from dataclasses doesn't recursively convert Union[int, Dict] properly. We need to manually serialize the relationships:

```python
# json_emitter.py - fix
def emit(self, functions, relationships):
    output_data = []

    for func in functions:
        func_index = None
        for idx, f in enumerate(functions):
            if f == func:
                func_index = idx
                break

        if func_index is None:
            continue

        parents, children = relationships.get(func_index, ([], []))

        # Manually serialize to preserve Union[int, Dict] structure
        output_entry = {
            "index": func_index,
            "self": {
                "path": func.path,
                "line": list(func.line_range),
                "type": "function",
                "name": func.name,
                "qualified_name": func.qualified_name,
                "brief": func.brief
            },
            "parents": self._serialize_relationships(parents),
            "children": self._serialize_relationships(children)
        }

        output_data.append(output_entry)

    json_output = json.dumps(output_data, indent=2, ensure_ascii=False)

    if self._output_file:
        with open(self._output_file, 'w', encoding='utf-8') as f:
            f.write(json_output)
    else:
        print(json_output)

def _serialize_relationships(self, rels: List[Union[int, Dict[str, Any]]]) -> List[Union[int, Dict[str, Any]]]:
    """Serialize relationship entries, preserving type markers."""
    serialized = []
    for rel in rels:
        if isinstance(rel, dict):
            # Copy dict to ensure it's serializable
            serialized.append(dict(rel))
        else:
            # Keep int as-is
            serialized.append(rel)
    return serialized
```

**Actually, looking more closely:** The current code uses `FunctionOutput` dataclass with `asdict()`. The Union type annotation should work. But let's be safe and implement the explicit serialization.

---

## Corrected Data Flow

### Step-by-Step Flow

```
┌─────────────────────────────────────────────────────────────────┐
│              CORRECTED DATA FLOW (After Fixes)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. cli.py - Feature Extraction Phase                           │
│     ├─> Loop over translation units                             │
│     ├─> For each TU:                                            │
│     │   └─> Create FeatureAnalyzer(tu, function_registry)       │
│     │   └─> Extract macros: analyzer.extract_macros()           │
│     │   └─> Extract pointers: analyzer.extract_function_pointers()│
│     │   └─> Extract classes: analyzer.extract_classes()         │
│     │   └─> Extract virtual methods: analyzer.extract_virtual_methods()│
│     │   └─> Merge analyzer.registry into feature_registry        │
│     └─> Build class derived relationships                      │
│         feature_registry.build_derived_relationships()           │
│                                                                  │
│  2. cli.py - Call Analysis Phase                                │
│     ├─> Initialize CallAnalyzer(function_registry, feature_registry)│
│     ├─> Initialize RelationshipBuilder(function_registry, call_analyzer)│
│     ├─> relationships = relationship_builder.build()            │
│     │                                                             │
│     │   Inside build():                                         │
│     │   ├─> For each function:                                  │
│     │   │   └─> calls = call_analyzer.analyze_calls(func)      │
│     │   │       │                                                │
│     │   │       Inside analyze_calls():                          │
│     │   │       ├─> Walk function cursor for CALL_EXPR          │
│     │   │       │   └─> For each CALL_EXPR:                     │
│     │   │       │       └─> Analyze direct/indirect/virtual calls│
│     │   │       │           ├─> If VAR_DECL/PARM_DECL:          │
│     │   │       │           │   └─> _analyze_function_pointer_call()│
│     │   │       │           │       ├─> Lookup in feature_registry│
│     │   │       │           │       └─> Return CallInfo with      │
│     │   │       │           │           is_indirect=True          │
│     │   │       │           │           possible_targets=[...]    │
│     │   │       │           ├─> If CXX_METHOD and virtual:       │
│     │   │       │           │   └─> _analyze_virtual_call()      │
│     │   │       │           │       ├─> Find base method          │
│     │   │       │           │       ├─> Find all derived classes  │
│     │   │       │           │       ├─> Collect all overrides    │
│     │   │       │           │       └─> Return CallInfo with      │
│     │   │       │           │           is_virtual=True           │
│     │   │       │           │           possible_targets=[...]    │
│     │   │       │           └─> Else: Direct call                │
│     │   │       │               └─> Return CallInfo with         │
│     │   │       │                   callee_index=...              │
│     │   │       │                                                │
│     │   │       ├─> If feature_registry exists:                  │
│     │   │       │   └─> Extract macro invocations                │
│     │   │       │       ├─> Create new FeatureAnalyzer(tu, reg) │
│     │   │       │       ├─> invocations = extract_macro_invocations(func_cursor)│
│     │   │       │       └─> For each invocation:                │
│     │   │       │           └─> _analyze_macro_call()           │
│     │   │       │               ├─> Lookup in feature_registry    │
│     │   │       │               └─> Return CallInfo with          │
│     │   │       │                   is_macro=True                 │
│     │   │       │                   callee_name="MACRO_NAME"     │
│     │   │       │                   callee_index=None             │
│     │   │       │                   macro_info=invocation         │
│     │   │       │                                                │
│     │   │       └─> Return list of CallInfo objects            │
│     │   │                                                            │
│     │   ├─> Convert CallInfo list to relationship entries         │
│     │   │   for call in calls:                                   │
│     │   │       ├─> If call.callee_index is not None:           │
│     │   │       │   └─> children.append({                        │
│     │   │       │       "index": call.callee_index,             │
│     │   │       │       "type": "direct"                        │
│     │   │       │   })                                          │
│     │   │       ├─> Elif call.possible_targets:                │
│     │   │       │   for target in call.possible_targets:        │
│     │   │       │       children.append({                        │
│     │   │       │           "index": target,                    │
│     │   │       │           "type": "indirect" if call.is_indirect else "virtual",│
│     │   │       │           "possible_targets": call.possible_targets  # if >1│
│     │   │       │       })                                      │
│     │   │       └─> Elif call.is_macro:                        │
│     │   │           children.append({                            │
│     │   │               "type": "macro",                        │
│     │   │               "name": call.callee_name                │
│     │   │           })                                          │
│     │   │                                                        │
│     │   ├─> Deduplicate children (all are now dicts)            │
│     │   │   unique_children = list(dict.fromkeys(               │
│     │   │       frozenset(entry.items()) for entry in children  │
│     │   │   ))                                                   │
│     │   │                                                        │
│     │   └─> Build parents (reverse lookup from children)       │
│     │                                                            │
│     └─> Return relationships dict                               │
│                                                                  │
│  3. cli.py - JSON Emission Phase                                │
│     ├─> emitter = JSONEmitter(output_path)                      │
│     ├─> emitter.emit(functions, relationships)                   │
│     │   │                                                        │
│     │   Inside emit():                                          │
│     │   ├─> For each function:                                  │
│     │   │   ├─> Get parents/children from relationships         │
│     │   │   └─> Create output dict:                              │
│     │   │       {                                               │
│     │   │           "index": func_index,                       │
│     │   │           "self": {...},                              │
│     │   │           "parents": self._serialize_relationships(parents),│
│     │   │           "children": self._serialize_relationships(children)│
│     │   │       }                                               │
│     │   │                                                        │
│     │   └─> Dump to JSON (indented, utf-8)                      │
│     │                                                            │
│     └─> Write to file or stdout                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Changes Required by File

### src/relationship_builder.py

**Change 1: Normalize entries to dicts before deduplication**

```python
# Add method to RelationshipBuilder class
def _normalize_entry(self, entry: Union[int, Dict[str, Any]]) -> Dict[str, Any]:
    """Convert entry to dict for consistent comparison and deduplication."""
    if isinstance(entry, dict):
        return entry
    return {"index": entry, "type": "direct"}

# Modify build() method
# Replace the loop that builds children list:
for call in calls:
    if call.callee_index is not None and call.callee_index != func_idx:
        children.append({
            "index": call.callee_index,
            "type": "direct"
        })
    elif call.possible_targets:
        for target_idx in call.possible_targets:
            if target_idx != func_idx:
                entry: Dict[str, Any] = {
                    "index": target_idx,
                    "type": "indirect" if call.is_indirect else "virtual"
                }
                if len(call.possible_targets) > 1:
                    entry["possible_targets"] = list(call.possible_targets)
                children.append(entry)
    elif call.is_macro:
        entry: Dict[str, Any] = {
            "type": "macro",
            "name": call.callee_name
        }
        if call.macro_info:
            entry["arguments"] = call.macro_info.arguments
        children.append(entry)

# Normalize and deduplicate
normalized_children = [self._normalize_entry(c) for c in children]
unique_children = list(dict.fromkeys(
    frozenset(entry.items()) for entry in normalized_children
))
children_map[func_idx] = unique_children
```

**Change 2: Update parents lookup to handle dict entries**

```python
# Modify the parents building loop:
for func_idx, func in enumerate(self._registry.get_all()):
    parents_map[func_idx] = []

    # Find functions that call this one
    for caller_idx, children in children_map.items():
        for child in children:
            # Handle dict entries
            if isinstance(child, dict):
                child_idx = child.get("index")
                if child_idx == func_idx:
                    parents_map[func_idx].append(caller_idx)
                    break
            elif child == func_idx:
                parents_map[func_idx].append(caller_idx)
                break
```

---

### src/json_emitter.py

**Change: Implement explicit relationship serialization**

```python
# Add method to JSONEmitter class
def _serialize_relationships(
    self,
    rels: List[Union[int, Dict[str, Any]]]
) -> List[Union[int, Dict[str, Any]]]:
    """
    Serialize relationship entries, preserving type markers.

    Args:
        rels: List of relationship entries (int or dict)

    Returns:
        Serialized list ready for JSON output
    """
    serialized: List[Union[int, Dict[str, Any]]] = []
    for rel in rels:
        if isinstance(rel, dict):
            # Copy dict to ensure it's serializable
            serialized.append(dict(rel))
        else:
            # Keep int as-is (though shouldn't exist after fixes)
            serialized.append(rel)
    return serialized

# Modify emit() method
# Replace the section that creates output_entry:
output_entry = {
    "index": func_index,
    "self": {
        "path": func.path,
        "line": list(func.line_range),
        "type": "function",
        "name": func.name,
        "qualified_name": func.qualified_name,
        "brief": func.brief
    },
    "parents": self._serialize_relationships(parents),
    "children": self._serialize_relationships(children)
}

output_data.append(output_entry)

# Remove FunctionOutput dataclass and asdict() usage
```

---

## Testing Strategy

### Unit Tests

**Test 1: RelationshipBuilder handles mixed call types**
```python
def test_relationship_builder_mixed_calls():
    """Test that direct, indirect, virtual, and macro calls are all preserved."""
    # Create mock CallInfo objects for different call types
    # Build relationships
    # Verify that all entries are dicts with correct type markers
    # Verify that deduplication works
```

**Test 2: RelationshipBuilder deduplication**
```python
def test_relationship_builder_deduplication():
    """Test that duplicate relationships are removed correctly."""
    # Create multiple CallInfo objects that reference the same target
    # Build relationships
    # Verify that duplicates are removed
```

**Test 3: JSONEmitter preserves type markers**
```python
def test_json_emitter_type_markers():
    """Test that type markers are preserved in JSON output."""
    # Create relationships with different call types
    # Emit JSON
    # Parse JSON and verify type markers are present
```

### Integration Tests

**Test 4: End-to-end macro calls**
```python
def test_end_to_end_macro_calls():
    """Test that macro invocations appear in call graph with correct markers."""
    # Create C file with macro invocations
    # Run analysis with --analyze-macros
    # Verify JSON output includes macro entries
```

**Test 5: End-to-end function pointers**
```python
def test_end_to_end_function_pointers():
    """Test that function pointer calls appear in call graph with correct markers."""
    # Create C file with function pointer calls
    # Run analysis with --analyze-pointers
    # Verify JSON output includes indirect markers
```

**Test 6: End-to-end virtual functions**
```python
def test_end_to_end_virtual_functions():
    """Test that virtual function calls appear in call graph with correct markers."""
    # Create C++ file with virtual function calls
    # Run analysis with --analyze-virtual
    # Verify JSON output includes virtual markers and possible_targets
```

---

## Known Limitations (Post-Fix)

### Function Pointer Target Resolution
**Issue:** Function pointer declarations are tracked, but assignments are not analyzed.

**Impact:** `possible_targets` for function pointers will always be empty unless manually populated.

**Future Work:**
1. Add assignment tracking to FeatureAnalyzer
2. When a function pointer is assigned a function value, record it
3. Build a mapping from pointer name to possible target functions

### Macro Expansion
**Issue:** Macro invocations are tracked, but macro expansion is not analyzed.

**Impact:** Cannot determine which function a macro wraps (by design - no heuristics).

**Future Work:**
1. Add preprocessing step to expand macros
2. Analyze expanded code for function calls
3. Track macro-to-function mappings

### Virtual Call Precision
**Issue:** All possible overrides are included, which may include false positives.

**Impact:** Call graph may include relationships that don't actually occur at runtime.

**Future Work:**
1. Add type flow analysis to narrow down possible types
2. Use RTTI hints if available
3. Add configuration options for conservative/precise resolution

---

## Success Criteria (Post-Fix)

1. **Macro calls appear in call graph**
   - [ ] Macro invocations are converted to dict entries with `type: "macro"`
   - [ ] Macro entries include `name` and `arguments` fields
   - [ ] No macro calls are lost during deduplication

2. **Type markers are preserved in JSON**
   - [ ] Direct calls have `type: "direct"` or implicit (int only)
   - [ ] Indirect calls have `type: "indirect"` and `possible_targets`
   - [ ] Virtual calls have `type: "virtual"` and `possible_targets`

3. **Relationship deduplication works**
   - [ ] Duplicate relationships are removed correctly
   - [ ] Mixed int/dict lists don't cause errors
   - [ ] All entries are normalized before comparison

4. **No regressions**
   - [ ] Existing direct call analysis still works
   - [ ] Performance impact is minimal
   - [ ] All existing tests pass

---

## Implementation Order

1. **Fix relationship_builder.py** (Priority 1)
   - Normalize entries to dicts before deduplication
   - Update parents lookup for dict entries

2. **Fix json_emitter.py** (Priority 1)
   - Implement explicit relationship serialization
   - Remove FunctionOutput dataclass dependency

3. **Add tests** (Priority 2)
   - Unit tests for RelationshipBuilder
   - Unit tests for JSONEmitter
   - Integration tests for end-to-end flows

4. **Update documentation** (Priority 3)
   - Document the integration fixes
   - Update PLAN.md with correct data flow
   - Add known limitations section

---

## Notes

- **No new features added** - this is purely integration fix
- **Architecture unchanged** - only data transformation at boundaries
- **Type system works** - Union[int, Dict] is correct, just needs proper handling
- **Deduplication strategy** - use `frozenset(entry.items())` for dict comparison
- **Future work** - function pointer assignment tracking is a separate feature

