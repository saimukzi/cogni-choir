# Development Conventions

## Branch Naming

Branches should follow the pattern: `type/YYYYMMDD-descriptive-name`

-   **type**: Standard commit type (e.g., `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`).
-   **YYYYMMDD**: The date of branch creation.
-   **descriptive-name**: A short, hyphenated description of the branch's purpose.

**Examples:**
-   `feat/20231027-user-authentication`
-   `fix/20231028-api-key-bug`
-   `docs/20231029-update-readme`

## Documentation

All python code should be documented in Google style.

## Forbidden python libraries

The following python libraries are forbidden and MUST NOT be used:

- google.generativeai: deprecated

## etc

- When illegal argument, raise ValueError
