# Backend-Frontend Integration Review

**Date**: May 20, 2026  
**Status**: 🔴 **CRITICAL ISSUES FOUND** - Integration will FAIL

---

## 🔴 Critical Integration Issues

### ISSUE-INT-01: Hardcoded API URLs (BLOCKER)
**Severity**: CRITICAL  
**Impact**: UI will fail to connect to backend in production/Docker

**Files Affected**:
1. `ui/src/components/ArtifactViewer.tsx` - Line 39
   - Uses: `http://localhost:8000/api/item/...`
   - Should use: `${apiUrl}/api/item/...`

2. `ui/src/components/CommentSection.tsx` - Line 20
   - Uses: `http://localhost:8000/api/item/...`
   - Should use: `${apiUrl}/api/item/...`

**Fix Required**: Both components must import `apiUrl` from `../config`

---

### ISSUE-INT-02: Missing KanbanColumn prop
**Severity**: MEDIUM  
**Impact**: TypeScript compilation error

**Problem**: `KanbanColumn` interface expects `id: string` but `App.tsx` passes `stage: string`

**Location**: `ui/src/components/KanbanColumn.tsx` line 54-58
```typescript
interface KanbanColumnProps {
  id: string;  // Should be 'stage' to match usage
  items: KanbanCardData[];
  onCardClick: (id: string) => void;
}
```

**Current Usage in App.tsx**:
```typescript
<KanbanColumn
  key={stage}
  stage={stage}  // ❌ Prop name mismatch
  items={...}
  onCardClick={...}
/>
```

---

## ✅ Integration Points That Work

### API Endpoints Mapping

| UI Action | HTTP Method | Endpoint | Backend Handler | Status |
|-----------|-------------|----------|-----------------|--------|
| Load board | GET | `/api/state` | `get_state()` | ✅ Ready |
| Move item | POST | `/api/move` | `move_item()` | ✅ Ready |
| Update item | PATCH | `/api/item/{id}` | `update_item()` | ✅ Ready |
| Create item | POST | `/api/items` | `create_item()` | ✅ Ready |
| Add comment | POST | `/api/item/{id}/comment` | `add_comment()` | ✅ Ready |
| Health check | GET | `/health` | `health_check()` | ✅ Ready |

### Data Model Consistency

| Field | Frontend Type | Backend Type | Match | Notes |
|-------|--------------|--------------|-------|-------|
| `id` | string | string | ✅ | Normalized to uppercase |
| `title` | string | string | ✅ | |
| `stage` | string | string | ✅ | Validated against VALID_STAGES |
| `priority` | string | string | ✅ | lowercase (after FIX-02) |
| `confidence_score` | number | number | ✅ | 0-100 |
| `description` | string? | string | ✅ | Optional, defaults to "" |
| `created_at` | string | string | ✅ | ISO 8601 format |
| `updated_at` | string | string | ✅ | ISO 8601 format |
| `comments` | Comment[] | Comment[] | ✅ | |

---

## 🔧 Required Fixes for Integration

### Fix 1: Update ArtifactViewer.tsx
```typescript
// Add at top of file
import { apiUrl } from '../config';

// Line 39 - Change from:
const res = await fetch(`http://localhost:8000/api/item/${itemId}/artifact/${name}`);

// To:
const res = await fetch(`${apiUrl}/api/item/${itemId}/artifact/${name}`);

// Line 56 - Change from:
const res = await fetch(`http://localhost:8000/api/item/${itemId}/artifact/${selectedArtifact.name}/content`, {

// To:
const res = await fetch(`${apiUrl}/api/item/${itemId}/artifact/${selectedArtifact.name}/content`, {
```

### Fix 2: Update CommentSection.tsx
```typescript
// Add at top of file
import { apiUrl } from '../config';

// Line 20 - Change from:
const res = await fetch(`http://localhost:8000/api/item/${itemId}/comment`, {

// To:
const res = await fetch(`${apiUrl}/api/item/${itemId}/comment`, {
```

### Fix 3: Fix KanbanColumn prop naming
**Option A** (Recommended): Rename interface prop
```typescript
interface KanbanColumnProps {
  stage: string;  // Changed from 'id'
  items: KanbanCardData[];
  onCardClick: (id: string) => void;
}
```

**Option B**: Update App.tsx to use 'id' prop
```typescript
<KanbanColumn
  key={stage}
  id={stage}  // Changed from 'stage'
  items={...}
  onCardClick={...}
/>
```

---

## 📋 Integration Test Checklist

### Pre-Integration Tests
- [ ] Fix ISSUE-INT-01 (hardcoded URLs)
- [ ] Fix ISSUE-INT-02 (prop naming)
- [ ] Verify `ui/src/config.ts` exists and exports `apiUrl`
- [ ] Verify backend has all required endpoints
- [ ] Verify Pydantic models match TypeScript interfaces

### Integration Tests
- [ ] Start backend: `python -m uvicorn api.main:app --reload`
- [ ] Start frontend: `cd ui && npm run dev`
- [ ] Test: Load board (GET `/api/state`)
- [ ] Test: Create new item (POST `/api/items`)
- [ ] Test: Move item between columns (POST `/api/move`)
- [ ] Test: Edit item details (PATCH `/api/item/{id}`)
- [ ] Test: Add comment (POST `/api/item/{id}/comment`)
- [ ] Test: View artifacts (GET `/api/item/{id}/artifact/{name}`)
- [ ] Test: Edit review.md (POST `/api/item/{id}/artifact/review.md/content`)
- [ ] Test: Drag and drop cards
- [ ] Test: Error handling (network errors, 404s, validation errors)

### Docker Integration Tests
- [ ] Build Docker images
- [ ] Test with Docker Compose
- [ ] Verify health check works
- [ ] Verify CORS settings
- [ ] Test frontend can reach backend container

---

## 🚀 Deployment Readiness

**Current Status**: ❌ **NOT READY**

**Blockers**:
1. ISSUE-INT-01 must be fixed (hardcoded URLs)
2. ISSUE-INT-02 must be fixed (prop mismatch)

**After Fixes**: ✅ **READY FOR INTEGRATION TESTING**

---

## 📝 Recommendations

1. **Immediate**: Fix the 2 critical issues
2. **Short-term**: Add integration tests
3. **Long-term**: Consider adding:
   - WebSocket for real-time updates
   - API client abstraction layer
   - Retry logic with exponential backoff
   - Request/response interceptors for logging

---

## 🔍 Summary

The backend and frontend are **90% ready** for integration, but the 2 critical issues will cause complete failure if not fixed:

- ✅ API endpoints are complete and match UI expectations
- ✅ Data models are consistent
- ✅ State management is thread-safe
- ❌ Hardcoded localhost URLs will break in production
- ❌ TypeScript prop mismatch will cause compilation error

**ETA to Integration-Ready**: 15 minutes (fix 2 files + update prop)
