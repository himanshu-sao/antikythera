# UI Refactoring Plan

## Current Issues Identified

1. **Monolithic App Component**: The main App.tsx file is too large (273 lines) with multiple responsibilities
2. **Test Failures**: Several tests are failing due to:
   - Parse error in App.test.tsx (string literal issue) - **RESOLVED**
   - Timeout issues in ArtifactViewer tests - **RESOLVED**
   - Polling test failures - **RESOLVED**
   - Mock mismatch/dependency chain issues in ArtifactViewer.edit.test.tsx - **IN PROGRESS**
3. **Missing Test Coverage**: No unit tests for key hooks like usePipelineState
4. **Component Coupling**: Components are tightly coupled with business logic

## Refactoring Goals

1. **Modularize App Component**:
   - Extract drag-and-drop logic into separate hooks
   - Extract modal management into custom hooks
   - Create dedicated components for different sections

2. **Improve Test Coverage**:
   - Add unit tests for hooks
   - Add UI component tests
   - Add functional/integration tests
   - Fix existing test failures (especially `ArtifactViewer.edit.test.tsx`)
   - Implement "Workflow Architect" and "Lifecycle Orchestrator" testing

3. **Enhance Code Structure**:
   - Create proper directory structure for components
   - Implement better state management patterns
   - Add proper error boundaries and loading states

## Proposed Structure

```
src/
├── components/
│   ├── kanban/
│   │   ├── KanbanBoard/
│   │   ├── KanbanColumn/
│   │   └── KanbanCard/
│   ├── modals/
│   │   ├── CreateItemModal/
│   │   ├── DeleteConfirmModal/
│   │   └── ManagementModals/
│   ├── artifact/
│   │   └── ArtifactViewer/
│   ├── editor/
│   │   └── CardEditor/
│   └── layout/
│       ├── Header/
│       └── SkeletonBoard/
├── hooks/
│   ├── usePipelineState.ts
│   ├── useModalManager.ts
│   ├── useDragAndDrop.ts
│   └── useArtifacts.ts
├── utils/
│   └── constants.ts
├── types/
│   └── index.ts
└── App.tsx (main orchestrator only)
```

## Test Strategy

1. **Unit Tests**:
   - Test individual hooks in isolation
   - Test pure functions and utilities
   - Test component rendering with different props

2. **Integration Tests**:
   - Test component interactions
   - Test API integration points
   - Test state management flows

3. **UI/Functional Tests**:
   - Test user interactions (drag/drop, clicks, form submissions)
   - Test responsive behavior
   - Test accessibility features

4. **End-to-End Tests**:
   - Test complete user workflows
   - Test error scenarios
   - Test loading states
