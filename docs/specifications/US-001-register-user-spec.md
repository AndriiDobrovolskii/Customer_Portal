# Specification: Register User

**Source:** docs/specifications/US-001 Register User.md
**Story ID:** US-001
**Generated:** 2026-08-15
**Status:** Draft (Open Questions resolved 2026-08-15)

## Summary

This spec covers registration of a new Visitor using email and password, including successful account creation and the validation/rejection rules the system must enforce (duplicate email, invalid email, weak password, missing password), plus the requirement that passwords never appear in API responses.

## Background

As a Visitor, I want to register using email and password so that I can create an account and access the Customer Portal.

## Functional Requirements

### FR-1: Successful Registration

Given a Visitor submits a valid, unregistered email and password, the system creates the user account and returns `HTTP 201 Created`, including:
- A `Location` header pointing to the created user resource (e.g., `/api/v1/users/{id}`).
- A JSON response body containing non-sensitive user metadata: `id`, `email`, `status` (`PENDING_VERIFICATION`), and `createdAt`.

**Derived from:** AC-1

### FR-2: Duplicate Email Rejection (Case-Insensitive)

Given an email address is already registered, the system rejects a registration attempt using the same email in any letter case (treating emails as identical regardless of case) and returns `HTTP 409 Conflict`. The submitted email is trimmed of leading/trailing whitespace before the duplicate check is applied. Email uniqueness is enforced at the data layer (e.g. a case-insensitive unique constraint/index), so this guarantee holds even when two registration requests for the same email are processed concurrently — at most one can succeed; the other receives `HTTP 409 Conflict`.

**Derived from:** AC-2; concurrency and whitespace handling per [Clarifications & Decisions](#clarifications--decisions)

### FR-3: Invalid or Missing Email Rejection

Given an email address that is missing, empty, or does not conform to RFC 5322 format, the system rejects the registration request and returns `HTTP 400 Bad Request` with validation error details. The submitted email is trimmed of leading/trailing whitespace before format validation is applied. The error payload uses the schema defined in [Validation Error Schema](#validation-error-schema).

**Derived from:** AC-3; error schema and whitespace handling per [Clarifications & Decisions](#clarifications--decisions)

### FR-4: Password Policy Enforcement

Given a password that does not meet the password policy (minimum 8 characters, containing at least 1 uppercase letter, 1 lowercase letter, 1 digit, and 1 special character), the system rejects the registration request and returns `HTTP 400 Bad Request` with validation error details. A "special character" is any ASCII printable, non-alphanumeric character (i.e. any of `!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~`). The error payload uses the schema defined in [Validation Error Schema](#validation-error-schema).

**Derived from:** AC-4; special-character set and error schema per [Clarifications & Decisions](#clarifications--decisions)

### FR-5: Missing Password Rejection

Given a registration request where the password field is missing or empty, the system rejects the request and returns `HTTP 400 Bad Request`.

**Derived from:** AC-5

### FR-6: Password Exclusion from Response

For any registration attempt, successful or failed, the API response payload must never contain the plaintext password or the password hash.

**Derived from:** AC-6 (the source's AC-1 cites this rule as "(per AC-5)," which is a mislabel — AC-5 is "Missing Password Rejection"; AC-6 is "Password Exclusion from Response" and is the actual source of this rule; see [Clarifications & Decisions](#clarifications--decisions))

## Clarifications & Decisions

The following points were left undefined by the source story (US-001) and were resolved by explicit stakeholder decision on 2026-08-15, rather than derived from AC text. They supersede the prior "Open Questions" section.

1. **AC-1/AC-5 reference mislabel** — AC-1's source text says the exclusion rule applies "(per AC-5)," but AC-5 is "Missing Password Rejection." Treated as a typo; the rule is sourced to AC-6 ("Password Exclusion from Response") instead. No behavior change — clarifies traceability only.
2. **Password special-character set** — Not exhaustively listed in AC-4 (only examples given). Decision: accept any ASCII printable, non-alphanumeric character. See FR-4.
3. **Validation error schema** — Not defined in AC-3/AC-4. Decision: use a field/message array, defined below. See [Validation Error Schema](#validation-error-schema).
4. **Concurrent duplicate registration** — Not addressed by AC-2. Decision: email uniqueness is enforced atomically at the data layer so concurrent requests for the same email cannot both succeed. See FR-2.
5. **Email whitespace handling** — Not addressed by AC-2/AC-3. Decision: leading/trailing whitespace is trimmed from the submitted email before format validation and duplicate-email checks. See FR-2, FR-3.

### Validation Error Schema

Applies to all `HTTP 400 Bad Request` responses referenced by FR-3 and FR-4:

```json
{
  "errors": [
    {
      "field": "email",
      "message": "Email address is not a valid RFC 5322 address.",
      "code": "INVALID_FORMAT"
    }
  ]
}
```

- `errors` is a non-empty array; one entry per violated rule.
- `field` is the name of the offending request field (`email` or `password`).
- `message` is a human-readable description of the violation.
- `code` is a stable, machine-readable identifier for the violation (e.g. `INVALID_FORMAT`, `REQUIRED`, `POLICY_VIOLATION`).

## Traceability Matrix

| AC ID | Acceptance Criterion (verbatim from source) | Covered by |
|-------|----------------------------------------------|------------|
| AC-1 | "Given a Visitor submits a valid, unregistered email and password, When the registration request is processed, Then the system creates the user account and returns `HTTP 201 Created` with: - A `Location` header pointing to the created user resource (e.g., `/api/v1/users/{id}`). - A JSON response body containing non-sensitive user metadata: ... - The response payload **must never** contain the password or password hash (per AC-5)." | FR-1, FR-6 |
| AC-2 | "Given an email address is already registered in the system (e.g., `user@example.com`), When a Visitor attempts to register using the same email with any combination of letter cases (e.g., `User@Example.com` or `USER@EXAMPLE.COM`), Then the system treats the emails as identical, rejects the request, and returns `HTTP 409 Conflict`." | FR-2 |
| AC-3 | "Given an email address that is missing, empty, or does not conform to standard RFC 5322 format, When a Visitor submits the registration request, Then the system rejects the request and returns `HTTP 400 Bad Request` with validation error details." | FR-3 |
| AC-4 | "Given a password that does not meet the password policy (minimum 8 characters, containing at least 1 uppercase, 1 lowercase, 1 digit, and 1 special character (e.g., @, #, $, %, !)), When a Visitor submits the registration request, Then the system rejects the request and returns `HTTP 400 Bad Request` with validation error details." | FR-4 |
| AC-5 | "Given a registration request where the password field is missing or empty, When a Visitor submits the request, Then the system rejects the request and returns `HTTP 400 Bad Request`." | FR-5 |
| AC-6 | "Given any registration attempt (successful or failed), When the API response is generated, Then the response payload must never contain the plaintext password or password hash." | FR-6 |