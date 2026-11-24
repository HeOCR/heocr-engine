# 0030 — Add an efficiency route to launch

- Status: accepted
- Date: 2026-11-24
- Decided by: Shay, the maintainer
- Amends: [0029](0029-open-and-closed-held-out-benchmarks.md)
- Retains: [0027 release hold](0027-model-release-hold.md) and [0028 contamination policy](0028-contamination-policy-v2.md)

## Decision

In at least one of the six registered document categories, HeOCR may qualify
for launch when its character error rate (CER) is within **5% relative** of the
best eligible comparator and it delivers **at least 2× the throughput** or
**at most half the fully loaded cost per 1,000 pages**. Both gates apply to
the same HeOCR configuration, category, deployment and registered real OPEN
held-out image panel. A single-carrier result supports a claim about that
carrier only.

The accuracy route in [0029](0029-open-and-closed-held-out-benchmarks.md)
continues, including its at-least-3% relative improvement threshold and
registered paired test. Modern printed unpointed Hebrew remains the primary
target. The release hold remains in force until one route qualifies and the
maintainer approves the exact release. The maintainer's separate approval
requirements for publication and release continue to apply.

## Evaluation

Freeze the candidate, eligible comparator roster, capture routes, operating
modes, image panel, and deployment before the held-out pass. Choose routes
and defaults on development data and record all effective component pins.
Report the full category scope, individual carrier strata, and applicable
exposure views.

On the registered filtered micro page CER, take the paired one-sided upper
confidence bound on `CER(HeOCR) − 1.05 × CER(comparator)` against every
eligible comparator. Require each bound to be at most zero. Resample
registered source clusters in pairs, keeping sister pages and captures
together. Pre-register familywise error control if multiple categories can
qualify in one pass.

Compare throughput and cost against the accuracy leader and any prespecified
reader statistically tied with it. Every such reader must be beaten by at
least one efficiency threshold, using a conservative lower bound on the
throughput ratio or upper bound on the cost ratio. Use simultaneous bounds
when either measure can qualify. Use at least three isolated, order-rotated
repeats on the same panel, with complete coverage, fixed CPU resources or a
stated cloud client and request policy. Record end-to-end pages per minute,
setup separately, and peak resident memory.

Price both arms at a stated workload and date in USD per 1,000 pages. Include
compute at equivalent paid-runner rates or evidenced on-premises amortization,
API usage at published rates, retries, and mandatory fees. Report memory,
pricing tier, service region, concurrency, and successful page counts. When
both arms have zero marginal cash cost, use the throughput test. A missing
required comparator or incomplete result leaves the category pending.

Use the public v0 images for runner checks and budget estimates. Preserve
historical accuracy scores and scope. Any qualifying claim names the
category, qualifying measure and deployment.
