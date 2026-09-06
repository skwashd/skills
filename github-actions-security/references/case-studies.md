# Case Studies — Why These Rules Exist

Each of these is a real 2026 incident that maps directly onto a rule in `SKILL.md`
(the `§` references below are to its sections). Cite them when a reviewer pushes back
on the cost of a rule.

## Trivy / `aquasecurity/trivy-action` — §1 and §2, and a lesson in incident response

A two-stage compromise, and the clearest argument in this skill.

**Stage one (February 2026)** was a textbook pwn request. A workflow used a privileged trigger
and checked out the fork pull request head, letting attacker-controlled code run with the base
repository's token. That is precisely the pattern §1 forbids and the one `actions/checkout` now
blocks by default.

**Stage two (March 2026)** was worse, and it was not another pwn request. After the first
disclosure, credentials were rotated — but the rotation **was not atomic**, and the attacker held
a valid token through the rotation window. They used it to force-push **76 of 77 version tags** in
`aquasecurity/trivy-action` to malicious commits. The blast radius reached the Trivy VSCode
extension, Docker images, and downstream PyPI packages.

Two lessons, and the second is the one people skip:

1. **Every consumer pinned to a tag was compromised. Every consumer pinned to a commit SHA was
   not.** §2 is not theoretical.
2. **Credential rotation that is not atomic is not rotation.** If an attacker can hold a live
   token across the rotation, you have announced the breach without ending it. Revoke first,
   verify revocation, then issue new credentials — and treat every artifact published during the
   exposure window as suspect until proven otherwise.

This is the incident behind §11's position that `aquasecurity/trivy-action` is not to be used.
The vulnerability was ordinary and forgivable; the handling was not. A supply-chain security
vendor that ships a pwn request, then botches the rotation badly enough to hand the attacker its
own tag namespace, has not earned a place in a trusted CI pipeline.

Note also that many published write-ups conflate the two stages and describe the March tag hijack
as itself a pwn request. It wasn't. Getting this right matters, because the two stages have
different fixes: §1 prevents stage one, and competent incident response prevents stage two.

## `actions-cool/issues-helper` — §2, as a controlled experiment

In May 2026 every tag in the repository was redirected to a single imposter commit, which pulled
down a runtime, scraped credentials from runner memory, and exfiltrated them. 53 tags moved.

What makes this worth citing is how cleanly it separated the two populations: **workflows pinned
to a known-good full commit SHA were unaffected; only those referencing version tags were
compromised.** Same action, same window, same attacker — the only variable was the pin. If
someone argues SHA pinning is cargo-culted ceremony, this is the answer.

The secondary lesson is about §1's ban on PR-commenting workflows: `issues-helper` exists to
comment on issues and PRs, which is exactly the capability that made it worth compromising and
exactly the capability §1 tells you not to grant a third-party action in the first place.
