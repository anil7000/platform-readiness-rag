# Synthetic platform readiness standard

## Workload reliability
Production-facing deployments generally need redundancy appropriate to their availability goals. A single replica is a review point; confirm an HPA is not managing capacity before changing replicas. Consider disruption budgets, topology spread and rollout settings separately. Static manifest checks cannot establish runtime reliability.

## Resource sizing
CPU and memory requests guide placement. Limits constrain consumption but can cause throttling or termination when chosen poorly. Start from measured workload demand and document exceptions. This starter policy asks for explicit requests and limits; CPU limits may require a documented exception for latency-sensitive services.

## Probes and immutable releases
Readiness controls traffic eligibility; liveness can restart an unhealthy container. Poor probes can worsen an incident. Use a startup probe for slow initialization when needed. Pin images to a known version or digest; latest is mutable. Track provenance in your delivery pipeline.

## Runtime security
Avoid privileged containers unless justified. Set runAsNonRoot and disable privilege escalation where supported. Host networking and host PID access increase the impact of compromise. Pod-level security defaults can apply to containers, with container overrides taking precedence. Inspect secrets management without sending secret values to a model.

This is an original starter policy for synthetic examples, not a security certification or comprehensive admission policy.
