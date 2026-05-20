# Hermes Kanban Enhancement Plan

## Date: 2026-05-20
## Status: Active Development
## Branch: kanban-fix

## Current Issues Identified

### ⚠️ ISSUE-1: Priority Badge Text Truncation
**Status**: Identified
**Severity**: MEDIUM
**Location**: `ui/src/components/KanbanColumn.tsx` - KanbanCard component

**Problem**: 
Priority badges appear cut off on cards, particularly visible on ID-004 where "Medium" text is truncated.

**Root Cause**:
Likely CSS flex/width constraints causing text overflow on the badge span element.

**Proposed Fix**:
```tsx
// Current (line ~29):
<span className={`text-xs px-2 py-1 rounded-full ${priorityColor}`}>
  {priority}
</span>

// Fix: Add whitespace-nowrap and ensure adequate padding:
<span className={`text-xs px-2 py-1 rounded-full whitespace-nowrap ${priorityColor}`}>
  {priority}
</span>
```

Or adjust the card flex layout to prevent squeezing:
```tsx
// Line ~38 - ensure flex container doesn't compress children:
<div className="flex justify-between items-start mb-2 gap-2">
```

---

### ⚠️ ISSUE-2: Confidence Score Display Missing Value
**Status**: Partially Fixed
**Severity**: LOW
**Location**: `ui/src/components/KanbanColumn.tsx` line 47

**Problem**:
Cards show "Confidence: %" instead of "Confidence: 0%" or actual numeric values.

**Root Cause**:
Old items in state.json lack the `confidence_score` field. TypeScript types were made optional but component doesn't provide default value.

**Fix**:
```tsx
// Current (line 47):
<span>Confidence: {confidence_score}%</span>

// Fix:
<span>Confidence: {confidence_score ?? 0}%</span>
```

---

### 🔴 ISSUE-3: Drag-and-Drop Not Working
**Status**: Investigating
**Severity**: HIGH
**Location**: `ui/src/App.tsx` + `ui/src/components/KanbanColumn.tsx`

**Problem**:
Cards cannot be dragged between columns. No visual feedback when attempting drag operation.

**Analysis**:
- Backend `/api/move` endpoint exists and is properly implemented
- Frontend `monitorForElements` is set up in App.tsx
- `draggable()` and `dropTargetForElements()` are called in KanbanCard and KanbanColumn
- Library: @atlaskit/pragmatic-drag-and-drop

**Possible Causes**:
1. Missing CSS for drag visuals
2. Event propagation issue (click handler interfering)
3. Library not properly initialized
4. Missing dependencies in useEffect

**Investigation Steps**:
1. Check browser console for errors
2. Verify @atlaskit/pragmatic-drag-and-drop is installed
3. Check if draggable elements have proper cursor styling
4. Test if onDragStart callbacks are firing

**Proposed Fixes**:
- Add dependency array to useEffect hooks in KanbanCard (currently missing `id`)
- Ensure cursor styles are applied: `cursor-grab` class
- Verify cleanup functions are being called
- Add debug logging to onDrop handler

---

## Enhancement Requests

### ⭐ ENH-NEW-01: Source Input Selection for Intake
**Status**: Planning
**Priority**: HIGH
**Requester**: User

**Requirement**:
When creating a new item in the INTAKE stage, provide:
1. Dropdown to select source type: "URL" or "Directory"
2. Dynamic text input field based on selection:
   - If "URL": Show URL input with placeholder "https://..."
   - If "Directory": Show path input with placeholder "/path/to/directory"
3. Store selection in item data model

**Implementation Plan**:

**Backend Changes**:
```python
# api/main.py - Update CreateItemRequest model:
class CreateItemRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default="", max_length=2000)
    priority: Optional[str] = Field(default="medium")
    source_type: Optional[str] = Field(default=None)  # NEW: "url" | "directory"
    source_value: Optional[str] = Field(default=None)  # NEW: actual URL or path
    
    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in ["url", "directory"]:
            raise ValueError('source_type must be "url" or "directory"')
        return v.lower() if v else None
```

**Frontend Changes**:
```tsx
// ui/src/types.ts - Update PipelineItem interface:
export interface PipelineItem {
  id?: string;
  title: string;
  stage: string;
  priority: string;
  confidence_score?: number;
  description?: string;
  source_type?: "url" | "directory";  // NEW
  source_value?: string;              // NEW
  // ... other fields
}
```

```tsx
// ui/src/components/CardEditor.tsx - Add form fields:
const [sourceType, setSourceType] = useState<string>(initialData.source_type || "");
const [sourceValue, setSourceValue] = useState<string>(initialData.source_value || "");

// In the form JSX:
<div className="mb-4">
  <label className="block text-sm font-medium text-gray-700 mb-1">Source Type</label>
  <select 
    value={sourceType}
    onChange={(e) => {
      setSourceType(e.target.value);
      setSourceValue(""); // Clear value when type changes
    }}
    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
  >
    <option value="">None</option>
    <option value="url">URL</option>
    <option value="directory">Directory</option>
  </select>
</div>

{sourceType && (
  <div className="mb-4">
    <label className="block text-sm font-medium text-gray-700 mb-1">
      {sourceType === "url" ? "Source URL" : "Source Directory"}
    </label>
    <input
      type="text"
      value={sourceValue}
      onChange={(e) => setSourceValue(e.target.value)}
      placeholder={sourceType === "url" ? "https://example.com" : "/path/to/directory"}
      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
    />
  </div>
)}
```

**Display in Card**:
```tsx
// ui/src/components/KanbanColumn.tsx - Show source icon/badge:
{source_type && (
  <div className="text-xs text-gray-500 mt-1">
    {source_type === "url" ? "🌐" : "📁"} {source_value}
  </div>
)}
```

**Files to Modify**:
1. `api/main.py` - Update CreateItemRequest, UpdateItemRequest
2. `api/state_manager.py` - Ensure new fields are persisted
3. `ui/src/types.ts` - Add source_type and source_value fields
4. `ui/src/components/CardEditor.tsx` - Add form inputs
5. `ui/src/components/KanbanColumn.tsx` - Display source info on card
6. `ui/src/components/ArtifactViewer.tsx` - Show source in detail view

---

## Implementation Sequence

### Phase 1: Critical Fixes (Immediate)
1. **FIX-CONFIDENCE**: Add `?? 0` to confidence_score display
2. **FIX-BADGE-LAYOUT**: Fix priority badge truncation with proper CSS
3. **DEBUG-DRAG-DROP**: Investigate and fix drag-drop functionality

### Phase 2: Source Selection Enhancement (Next)
4. **ENH-SOURCE-BACKEND**: Add source_type and source_value fields to backend
5. **ENH-SOURCE-FRONTEND**: Implement dropdown and dynamic input in CardEditor
6. **ENH-SOURCE-DISPLAY**: Show source info on cards and detail view

### Phase 3: Testing & Documentation
7. Test all features on localhost:5173
8. Update INT_REPORT.md with latest status
9. Update PROJECT_SUMMARY.md with enhancement implementation

---

## Testing Checklist

**Phase 1 Validation**:
- [ ] Confidence values show "0%" instead of "%"
- [ ] Priority badges display full text without truncation
- [ ] Cards can be dragged between columns
- [ ] Drag-drop updates persist to backend
- [ ] UI updates optimistically during drag

**Phase 2 Validation**:
- [ ] Source type dropdown appears in card editor
- [ ] Input field changes based on dropdown selection
- [ ] URL validation works for URL source type
- [ ] Path validation works for directory source type
- [ ] Source info displays on card (icon + truncated value)
- [ ] Source info shows in detail modal
- [ ] Data persists across refresh

---

## Next Actions

**For Developer**:
1. Run `git pull origin kanban-fix` to get latest changes
2. Start with Phase 1 fixes (quick wins)
3. Test drag-drop in browser console to identify error
4. Implement source selection (Phase 2) after Phase 1 complete

**Estimated Time**:
- Phase 1: 30-60 minutes
- Phase 2: 1-2 hours
- Phase 3: 30 minutes

**Total**: ~3 hours
