# S7B artifacts

Compact aggregate scientific artifacts only: identities, digests, lengths and
verdicts.

Raw response bytes live under `../evidence/`, never here. No artifact in this
directory may contain an Authorization header, a credential value, a credential
digest, or a base64 copy of the raw response body.
