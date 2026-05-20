# Kanban Fixes - Complete Review (May 20, 2026)

This document catalogs all identified issues in the kanban-fix branch and their resolutions, based on best practices from popular open-source kanban implementations (Trello, Jira, react-beautiful-dnd, @atlaskit/pragmatic-drag-and-drop).

---

## ✅ Fixed Issues

### FIX-01: Missing `stage` field in KanbanCardData interface
**Issue**: TypeScript interface incomplete
**Location**: `ui/src/types.ts`
**Fix**: Added `stage: string;` to KanbanCardData
**Status**: ✅ Complete
**Commit**: `fix(types): add missing stage field to KanbanCardData interface`

---

## 🔧 Remaining Issues & Recommended Fixes

### FIX-02: Priority field case inconsistency
**Issue**: KanbanColumn expects `Priority` (capitalized) but backend/API uses `priority` (lowercase)
**Impact**: Cards won't show correct priority colors
**Location**: `ui/src/components/KanbanColumn.tsx` line 36
**Fix Required**:
```typescript
// Change from:
const priorityColor = {
  High: 'bg-red-100 text-red-800',
  Medium: 'bg-yellow-100 text-yellow-800',
  Low: 'bg-green-100 text-green-800',
}[priority] || 'bg-gray-100 text-gray-800';

// To (lowercase keys):
const priorityColor = {
  high: 'bg-red-100 text-red-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-green-100 text-green-800',
  critical: 'bg-purple-100 text-purple-800', // Add critical
}[priority?.toLowerCase()] || 'bg-gray-100 text-gray-800';
```

### FIX-03: create_item missing required fields
**Issue**: StateManager.create_item doesn't initialize `priority` or `confidence_score`
**Impact**: New items will have `undefined` for these fields, breaking UI
**Location**: `api/state_manager.py` line 43-58
**Fix Required**:
```python
items[item_id] = {
    "title": title,
    "stage": "INTAKE",
    "priority": "medium",  # Add default
    "confidence_score": 0,  # Add default
    "order": order,
    "created_at": datetime.utcnow().isoformat() + "Z",
    "updated_at": datetime.utcnow().isoformat() + "Z",
    "comments": [],
    "history": [{"stage": "INTAKE", "at": datetime.utcnow().isoformat() + "Z"}],
}
```

### FIX-04: Column titles not user-friendly
**Issue**: Columns show raw IDs like "REVIEW_SPEC" instead of "Review Spec"
**Impact**: Poor UX
**Location**: `ui/src/components/KanbanColumn.tsx` line 80
**Fix Required**:
```typescript
const stageTitles: Record<string, string> = {
  INTAKE: 'Intake',
  REFINEMENT: 'Refinement',
  REVIEW_SPEC: 'Review Spec',
  ARCHITECTURE: 'Architecture',
  REVIEW_ARCH: 'Review Arch',
  TESTING: 'Testing',
  REVIEW_TEST: 'Review Test',
  APPROVED: 'Approved',
  EXECUTING: 'Executing',
  DONE: 'Done',
};

const displayTitle = stageTitles[id] || id;

// Then use {displayTitle} instead of {id}
```

### FIX-05: Missing description field in PipelineItem
**Issue**: Type definition has `description` but not marked as optional
**Location**: `ui/src/types.ts`
**Fix Required**: Add `description?: string;` as optional field

### FIX-06: KanbanColumn missing key prop warnings
**Issue**: React performance - items.map needs unique keys
**Location**: `ui/src/components/KanbanColumn.tsx` line 103
**Current**: Already correct with `key={item.id}`
**Status**: ✅ Already handled correctly

### FIX-07: State manager missing default for `description`
**Issue**: update_item allows description but create_item doesn't initialize it
**Location**: `api/state_manager.py`
**Fix Required**: Add `"description": ""` to create_item

### FIX-08: App.tsx creates items with wrong priority casing
**Issue**: App.tsx sets `priority: 'medium'` but should match backend format
**Location**: `ui/src/App.tsx` line 132
**Status**: ✅ Already correct (lowercase 'medium')

---

## 📚 Best Practices Applied (from Trello/Jira)

### Already Implemented ✅
1. **Optimistic Updates**: Cards appear immediately (ENH-09)
2. **Visual Feedback**: Drag opacity changes, hover states
3. **Error Boundaries**: React error recovery (ENH-04)
4. **Loading States**: Spinner and skeleton screens (ENH-05)
5. **Thread Safety**: Backend state locking (ENH-03)
6. **Atomic Writes**: Crash-safe file operations

### Recommended Additions (Future)
1. **Keyboard Navigation**: Arrow keys for card selection
2. **Card Filtering**: Search by title, filter by priority
3. **Batch Operations**: Select multiple cards, bulk move
4. **Undo/Redo**: Action history stack
5. **Real-time Sync**: WebSocket for multi-user
6. **Card Templates**: Pre-defined card structures
7. **Swimlanes**: Group by assignee or priority
8. **Archive/Restore**: Soft delete instead of hard delete

---

## 🎨 UI/UX Issues

### Issue 1: No empty state messaging
**Fix**: Add "No items" placeholder in empty columns
```tsx
{items.length === 0 ? (
  <div className="text-center text-gray-400 py-8">
    <p className="text-sm">No items yet</p>
    <p className="text-xs mt-1">Drag cards here</p>
  </div>
) : items.map(...)
```

### Issue 2: No loading indicator on drag
**Fix**: Already handled via opacity-50 class

### Issue 3: No confirmation for delete
**Fix**: Add modal confirmation before delete

---

## 🔒 Security Considerations

### Already Secure ✅
1. Input validation via Pydantic (ENH-02)
2. Path traversal prevention in artifact endpoints
3. ID sanitization (uppercase, regex validation)

### Recommended
1. **Rate limiting**: Prevent API abuse
2. **CSRF tokens**: If adding authentication
3. **Content-Type validation**: Ensure JSON payloads

---

## 🚀 Performance Optimizations

### Already Optimized ✅
1. React.memo candidates identified
2. useCallback for event handlers
3. Atomic file writes prevent corruption

### Recommended
1. **Pagination**: Load items in batches if >100 items
2. **Virtual scrolling**: For long columns (react-window)
3. **Debounce search**: If adding filter
4. **IndexedDB cache**: Offline-first PWA

---

## 📝 Documentation Gaps

1. ❌ No API endpoint documentation (add OpenAPI/Swagger)
2. ❌ No component prop documentation (add JSDoc)
3. ✅ PROJECT_SUMMARY.md exists and is comprehensive
4. ❌ No developer setup guide (add CONTRIBUTING.md)

---

## ✅ Summary

**Critical Fixes Required**: 4 (FIX-02, FIX-03, FIX-04, FIX-05, FIX-07)  
**Nice-to-Have**: 3 (empty states, confirmations, docs)  
**Already Excellent**: 9+ (error handling, validation, thread safety, etc.)

**Overall Assessment**: The kanban implementation is **production-ready** after the 4 critical fixes. The architecture follows best practices and includes features often missing in basic kanban boards (optimistic updates, error boundaries, atomic writes).
