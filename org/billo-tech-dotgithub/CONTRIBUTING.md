# Contributing to Billo Tech projects

Thanks for helping. A few rules keep the repositories easy to trust.

1. **One canonical home per project.** Engine work goes to `LOCI-MEMORY-ENGINE`, runtime work to `arc`, papers to `loci-card-papers`. Do not start a new copy of an existing repo.
2. **Branches:** `main` is the only long-lived branch. Name feature branches `<area>/<short-description>` (for example `engine/heat-rescale`) and open a pull request.
3. **Tests:** run `python -m pytest` before you open a PR. New behaviour needs a test; documented examples belong in `tests/test_e2e_smoke.py`.
4. **No secrets.** Never commit tokens, keys, private `.env` files or host details.
5. **Nothing is deleted.** Prefer superseding to deleting, in code as in memory. Removing files needs evidence in the PR (a hash match, a reference search, or the commit that made it obsolete).
6. **AI contributors** are welcome and credited in `AUTHORS.md`. Agent-written PRs follow the same rules and need a human review before merge.

Code is contributed under the MIT License of the repository you contribute to.
