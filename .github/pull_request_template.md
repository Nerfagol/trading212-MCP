## Summary

Describe the user-visible or operational change and why it is needed.

## Verification

- [ ] `ruff check .`
- [ ] `mypy src tests`
- [ ] `pytest`
- [ ] `python -m build`
- [ ] `docker build .`

## Read-only security review

- [ ] The exact eight MCP tools remain read-only.
- [ ] No POST, PUT, PATCH, DELETE, generic request/proxy method, or Trading 212 write path was added.
- [ ] No buying, selling, order placement, creation, cancellation, update, or modification was added.
- [ ] No credentials, `.env` files, Authorization headers, or financial account data are included.
- [ ] QNAP and tunnel network bindings remain private.
