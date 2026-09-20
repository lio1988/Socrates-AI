# Security branch decisions

The HTTP application is single-operator, local-only by default. Remote access
requires a separate password, allowed hosts and HTTPS. Provider API keys must
never be used as application passwords. All endpoints share the access boundary.

Do not copy private environment files, local snapshot history, or unrelated G4
work into this branch. HTML responses and provider errors remain secret-safe.
Source publication is not production deployment or proof of comprehensive safety.
