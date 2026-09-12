"""Review Kubernetes workload exports against an explicit starter platform standard."""
TITLE = "Platform Readiness RAG"
DEFAULT_QUESTION = "Review Kubernetes platform readiness: resources, probes, replicas, image pinning, security context and rollout reliability."

def analyze(data):
    if not isinstance(data, dict):
        raise ValueError("Expected a Kubernetes JSON object or List")
    items = data.get("items") if data.get("kind") == "List" else [data]
    if not isinstance(items, list):
        raise ValueError("Kubernetes List requires items")
    findings, checked, skipped = [], [], []
    def flag(code, severity, resource, detail):
        findings.append({"code": code, "severity": severity, "resource": resource,
                         "message": resource + ": " + detail})
    for obj in items:
        if not isinstance(obj, dict):
            raise ValueError("Each Kubernetes item must be an object")
        kind = obj.get("kind")
        meta = obj.get("metadata", {})
        resource = f"{meta.get('namespace', 'default')}/{kind}/{meta.get('name', 'unnamed')}"
        if kind not in {"Deployment", "StatefulSet", "DaemonSet", "Pod"}:
            skipped.append(resource)
            continue
        spec = obj.get("spec", {})
        pod = spec if kind == "Pod" else spec.get("template", {}).get("spec", {})
        containers = pod.get("containers")
        if not isinstance(containers, list) or not containers:
            raise ValueError(resource + " requires containers")
        checked.append(resource)
        if kind in {"Deployment", "StatefulSet"}:
            replicas = spec.get("replicas", 1)
            if type(replicas) is not int or replicas < 0:
                raise ValueError("replicas must be a nonnegative integer")
            if replicas < 2:
                flag("LOW_REPLICAS", "review", resource,
                     f"{replicas} replicas configured; evaluate availability requirements and any HPA.")
        if pod.get("hostNetwork") or pod.get("hostPID"):
            flag("HOST_ACCESS", "high", resource, "Host network/PID access is enabled.")
        for container in containers:
            if not isinstance(container, dict) or not isinstance(container.get("name"), str):
                raise ValueError("Container requires a name")
            name = resource + "/" + container["name"]
            image = container.get("image", "")
            last = image.rsplit("/", 1)[-1]
            if not image or (":" not in last and "@sha256:" not in image) or last.endswith(":latest"):
                flag("MUTABLE_IMAGE", "review", name, "Image is missing or uses latest/implicit latest; pin a version or digest.")
            resources = container.get("resources", {})
            for level in ("requests", "limits"):
                for unit in ("cpu", "memory"):
                    value = resources.get(level, {}).get(unit)
                    if value is None or str(value).strip() in {"", "0", "0m", "0Mi", "0Gi"}:
                        flag("RESOURCE_" + level.upper(), "review", name,
                             f"Missing/nonpositive {unit} {level}; validate resource sizing policy.")
            for probe in ("readinessProbe", "livenessProbe"):
                if not container.get(probe):
                    flag("MISSING_PROBE", "review", name, f"{probe} is absent; assess application-specific probe behavior.")
            security = dict(pod.get("securityContext", {}))
            security.update(container.get("securityContext", {}))
            if security.get("privileged") is True:
                flag("PRIVILEGED", "critical", name, "Container runs privileged.")
            if security.get("runAsNonRoot") is not True:
                flag("NON_ROOT_UNSET", "review", name, "runAsNonRoot is not explicitly true.")
            if security.get("allowPrivilegeEscalation") is not False:
                flag("ESCALATION_UNSET", "review", name, "allowPrivilegeEscalation is not explicitly false.")
        # No env values or secrets are copied into the analysis output.
    if not checked:
        flag("NO_SUPPORTED_WORKLOADS", "unknown", "input",
             "No supported workloads were found; readiness cannot be assessed.")
    counts = {s: sum(f["severity"] == s for f in findings) for s in ("critical", "high", "review", "unknown")}
    return {"checked_workloads": checked, "skipped_resources": skipped, "severity_counts": counts,
            "findings": findings, "assessment": "needs-review" if findings else "starter-checks-passed",
            "limitations": ["Static export review; no live health or admission policy verification.",
                            "HPA, PDB, NetworkPolicy matching, init containers and Jobs are outside this version.",
                            "Resource quantity syntax is not fully validated."]}
