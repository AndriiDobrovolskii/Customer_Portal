## **US-1.1 Register User**

#### **User Story**

As a Visitor

I want to register using email and password

so that I can create an account and access the Customer Portal.

|  |  |
| :---- | :---- |
|  |  |

 

# **Acceptance Criteria**

# Acceptance Criteria

### AC-1: Successful Registration
Given a Visitor submits a valid, unregistered email and password,
When the registration request is processed,
Then the system creates the user account and returns `HTTP 201 Created` with:
  - A `Location` header pointing to the created user resource (e.g., `/api/v1/users/{id}`).
  - A JSON response body containing non-sensitive user metadata:
    ```json
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "email": "user@example.com",
      "status": "PENDING_VERIFICATION",
      "createdAt": "2026-08-15T10:00:00Z"
    }
    ```
  - The response payload **must never** contain the password or password hash (per AC-5).

### AC-2: Duplicate Email Rejection (Case-Insensitive)
Given an email address is already registered in the system (e.g., `user@example.com`),
When a Visitor attempts to register using the same email with any combination of letter cases (e.g., `User@Example.com` or `USER@EXAMPLE.COM`),
Then the system treats the emails as identical, rejects the request, and returns `HTTP 409 Conflict`.

### AC-3: Invalid or Missing Email Rejection
Given an email address that is missing, empty, or does not conform to standard RFC 5322 format,
When a Visitor submits the registration request,
Then the system rejects the request and returns `HTTP 400 Bad Request` with validation error details.

### AC-4: Password Policy Enforcement
Given a password that does not meet the password policy (minimum 8 characters, containing at least 1 uppercase, 1 lowercase, 1 digit, and 1 special character (e.g., @, #, $, %, !)),
When a Visitor submits the registration request,
Then the system rejects the request and returns `HTTP 400 Bad Request` with validation error details.

### AC-5: Missing Password Rejection
Given a registration request where the password field is missing or empty,
When a Visitor submits the request,
Then the system rejects the request and returns `HTTP 400 Bad Request`.

### AC-6: Password Exclusion from Response
Given any registration attempt (successful or failed),
When the API response is generated,
Then the response payload must never contain the plaintext password or password hash.