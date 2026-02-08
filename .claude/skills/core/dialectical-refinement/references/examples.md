# Refinement Examples

## Before and After

### Example 1: Vague Feature Request

**Before Refinement:**
```
Title: Add caching to API

Description: We should add caching to make the API faster.
```

**After Refinement:**
```
Title: Add memoization for get-users endpoint

Description:
Memoize get-users responses with 5-minute TTL.
~40 lines across 2 files.

Design:
- Add memoization wrapper to src/app/cache.py
- Apply to get_users in src/app/api.py
- Cache key format: "users-list-{query-hash}"

Acceptance Criteria:
1. Second call within 5 min returns cached response
2. Cache miss logs to console
3. Cache can be bypassed with no_cache option
4. Errors don't cache (only successful responses)

Out of Scope:
- Cache invalidation on user changes (future task)
- Caching other endpoints (separate tasks per endpoint)
- Distributed cache (not needed for this use case)

Complexity: m
Labels: [refined]
```

### Example 2: Epic Breakdown

**Before:**
```
Title: User Authentication System
Type: epic
Description: Add login/logout functionality
```

**After Breakdown:**
```
Epic: User Authentication System (refined)
|- Task: Add password hashing utility (xs, refined)
|- Task: Create User model with auth fields (s, refined)
|- Task: Implement login endpoint (m, needs-refinement)
|- Task: Implement logout endpoint (s, refined)
|- Task: Add session middleware (m, needs-refinement)
|- Task: Create login UI component (m, needs-refinement)

Dependencies:
- Login endpoint blocks Logout endpoint
- User model blocks Login endpoint
- Password hashing blocks User model
```

## The Dialectical Arc

| Pass | Role | Cognitive Mode |
|------|------|----------------|
| 1. Formalize | Thesis | Analysis |
| 2. Simplify | Antithesis | Criticism |
| 3. Challenge | Antithesis to antithesis | Advocacy |
| 4. Synthesize | Synthesis | Integration |

This mirrors classical dialectical reasoning - structured tension that surfaces and resolves conflicts *before* code is written.
