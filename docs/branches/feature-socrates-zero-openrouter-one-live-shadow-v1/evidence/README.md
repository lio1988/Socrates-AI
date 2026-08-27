# S7B live evidence

Raw, unnormalized evidence from the single live shadow call: the exact response
bytes and response headers as received, before anything interprets them.

Kept separate from `../artifacts/` so that aggregate artifacts can reference
evidence by digest instead of duplicating it. Nothing here may contain the
Authorization header or any credential material.
