# Development Conventions

## Branch Naming

Branches should follow the pattern: `YYYYMMDD/type/descriptive-name`

-   **type**: Standard commit type (e.g., `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`).
-   **YYYYMMDD**: The date of branch creation.
-   **descriptive-name**: A short, hyphenated description of the branch's purpose.

**Examples:**
-   `20231027/feat/user-authentication`
-   `20231028/fix/api-key-bug`
-   `20231029/docs/update-readme`

## Documentation

All python code should be documented in Google style.

## Forbidden python libraries

- Do not use google-generativeai.  google-generativeai is deprecated.  Use google-genai instead.
- Do not use google.generativeai .  google.generativeai is deprecated.  Use google.genai instead.

## etc

- When illegal argument, raise ValueError
