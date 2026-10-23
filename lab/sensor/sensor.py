"""
lab/sensor/sensor.py

Live sensor for the Docker lab.

It shares the victim container's network, so it sees every packet going to and from
the victim. It groups packets into connections ("flows"), builds the 41 NSL-KDD features
for each finished flow, and posts them to the API's POST /respond endpoint.

Honest limits (read these when results look odd):
  - 28 of the 41 features come from packet headers and timing, and are computed here.
  - The 13 "content" features (failed logins, root shell, ...) need payload inspection.
    They are set to 0, except logged_in, which is a simple guess.
  - NSL-KDD is old traffic, so some live flows may be labeled unexpectedly. Use
    VERBOSE=1 to print the features and compare them with what the model learned.

Settings come from environment variables (see the constants below).
"""

import collections
import csv
import json
import os
import queue
import socket
import threading
import time

import requests
from scapy.all import sniff, get_if_addr, IP, TCP, UDP, ICMP, Raw, conf

conf.verb = 0

# ------------------------------------------------------------------ settings
API_URL = os.environ.get("API_URL", "http://api:8000").rstrip("/")
IFACE = os.environ.get("SENSOR_IFACE", "eth0")
FLOW_TIMEOUT = float(os.environ.get("FLOW_TIMEOUT", "1.5"))    # seconds of silence that ends a flow
TIME_WINDOW = float(os.environ.get("TIME_WINDOW", "2.0"))      # window for the "count" style features
HOST_WINDOW = int(os.environ.get("HOST_WINDOW", "255"))        # last N connections for dst_host_* features
POST_WORKERS = int(os.environ.get("POST_WORKERS", "6"))        # parallel posts to the API
QUEUE_SIZE = int(os.environ.get("QUEUE_SIZE", "300"))          # flows waiting to be posted
INSTANCE_ID = os.environ.get("INSTANCE_ID", "victim")
SERVICE_ID = os.environ.get("SERVICE_ID", "victim-web")
EXCLUDE_HOSTS = [h.strip() for h in os.environ.get("EXCLUDE_HOSTS", "api,dashboard").split(",") if h.strip()]
VERBOSE = os.environ.get("VERBOSE", "0") == "1"                # print features of the first flows
VERBOSE_LIMIT = int(os.environ.get("VERBOSE_LIMIT", "30"))
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"                # compute features, do not post
RECORD_CSV = os.environ.get("RECORD_CSV", "")                  # append every flow's features to this file
CLOSED_MEMORY = 60.0                                           # ignore late packets of a finished flow

FEATURE_ORDER = [
    "duration", "protocol_type", "service", "flag", "src_bytes", "dst_bytes", "land",
    "wrong_fragment", "urgent", "hot", "num_failed_logins", "logged_in", "num_compromised",
    "root_shell", "su_attempted", "num_root", "num_file_creations", "num_shells",
    "num_access_files", "num_outbound_cmds", "is_host_login", "is_guest_login", "count",
    "srv_count", "serror_rate", "srv_serror_rate", "rerror_rate", "srv_rerror_rate",
    "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate", "dst_host_count",
    "dst_host_srv_count", "dst_host_same_srv_rate", "dst_host_diff_srv_rate",
    "dst_host_same_src_port_rate", "dst_host_srv_diff_host_rate", "dst_host_serror_rate",
    "dst_host_srv_serror_rate", "dst_host_rerror_rate", "dst_host_srv_rerror_rate",
]

# Port -> NSL-KDD service name. Unlisted ports are "private", like the dataset.
TCP_SERVICES = {
    7: "echo", 9: "discard", 11: "systat", 13: "daytime", 15: "netstat", 20: "ftp_data", 21: "ftp",
    22: "ssh", 23: "telnet", 25: "smtp", 37: "time", 42: "name", 43: "whois", 53: "domain",
    70: "gopher", 71: "remote_job", 77: "rje", 79: "finger", 80: "http", 84: "ctf", 95: "supdup",
    101: "hostnames", 102: "iso_tsap", 105: "csnet_ns", 109: "pop_2", 110: "pop_3", 111: "sunrpc",
    113: "auth", 117: "uucp_path", 119: "nntp", 137: "netbios_ns", 139: "netbios_ssn", 143: "imap4",
    150: "sql_net", 175: "vmnet", 179: "bgp", 194: "IRC", 210: "Z39_50", 245: "link", 389: "ldap",
    433: "nnsp", 443: "http_443", 512: "exec", 513: "login", 514: "shell", 515: "printer",
    520: "efs", 530: "courier", 540: "uucp", 543: "klogin", 544: "kshell", 1911: "mtp",
    2784: "http_2784", 6000: "X11", 8001: "http_8001",
}
UDP_SERVICES = {53: "domain_u", 69: "tftp_u", 123: "ntp_u", 137: "netbios_ns", 138: "netbios_dgm"}
SERROR_FLAGS = {"S0", "S1", "S2", "S3"}
RERROR_FLAGS = {"REJ"}

# ------------------------------------------------------------------- state
LOCK = threading.Lock()
FLOWS = {}                                         # open flows by key
CLOSED = {}                                        # key -> time until which late packets are ignored
HISTORY = collections.deque(maxlen=5000)           # finished flows, newest last
QUEUE = queue.Queue(maxsize=QUEUE_SIZE)
STATS = collections.Counter()
STATS_LOCK = threading.Lock()
CSV_LOCK = threading.Lock()
LOCAL_IP = "0.0.0.0"
EXCLUDED = set()


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Flow:
    """One connection, seen from the victim's side. 'in' = toward the victim."""

    def __init__(self, key, start, remote_ip, remote_port, local_port, proto):
        self.key = key
        self.start = start
        self.last = start          # last activity, used for the idle timeout
        self.end = start           # last real packet, used for duration
        self.remote_ip, self.remote_port, self.local_port, self.proto = remote_ip, remote_port, local_port, proto
        self.src_bytes = 0         # payload bytes from the remote host to the victim
        self.dst_bytes = 0         # payload bytes from the victim to the remote host
        self.syn = self.synack = self.ack_hs = False
        self.fin_in = self.fin_out = self.rst_in = self.rst_out = False
        self.urgent = 0
        self.fragments = 0


def service_name(proto, local_port):
    if proto == "tcp":
        return TCP_SERVICES.get(local_port, "private")
    if proto == "udp":
        return UDP_SERVICES.get(local_port, "private")
    return "eco_i"


def tcp_flag(f):
    """NSL-KDD connection state (SF, S0, REJ, RSTO, ...) from what was seen."""
    if f.proto != "tcp":
        return "SF"
    if not f.syn:
        return "OTH"                      # joined mid-connection
    if f.rst_out and not f.synack:
        return "REJ"                      # SYN answered with a reset (closed port)
    if f.rst_in:
        return "RSTO"                     # the remote side aborted
    if f.rst_out:
        return "RSTR"
    if not f.synack or not f.ack_hs:
        return "S0"                       # handshake never completed (half-open)
    if f.fin_in and f.fin_out:
        return "SF"                       # normal start and finish
    if f.fin_in:
        return "S2"
    if f.fin_out:
        return "S3"
    return "S1"


# -------------------------------------------------------------- features
def rate(items, pred):
    return round(sum(1 for r in items if pred(r)) / len(items), 4) if items else 0.0


def compute_features(rec):
    """Build the 41 features for a finished flow. Called with LOCK held; rec is already in HISTORY."""
    history = list(HISTORY)

    # 2-second window: connections to this host that started in the last TIME_WINDOW seconds
    window = [r for r in history if rec["start"] - TIME_WINDOW <= r["start"] <= rec["start"]]
    window_srv = [r for r in window if r["service"] == rec["service"]]
    count, srv_count = len(window), len(window_srv)

    # host window: the last HOST_WINDOW connections to this host
    hosts = history[-HOST_WINDOW:]
    hosts_srv = [r for r in hosts if r["service"] == rec["service"]]

    serr = lambda r: r["flag"] in SERROR_FLAGS
    rerr = lambda r: r["flag"] in RERROR_FLAGS
    other_host = lambda r: r["src_ip"] != rec["src_ip"]

    feats = {
        "duration": rec["duration"], "protocol_type": rec["proto"], "service": rec["service"],
        "flag": rec["flag"], "src_bytes": rec["src_bytes"], "dst_bytes": rec["dst_bytes"],
        "land": 0, "wrong_fragment": rec["wrong_fragment"], "urgent": rec["urgent"],
        # content features need payload inspection: left at 0 (logged_in is a guess)
        "hot": 0, "num_failed_logins": 0, "logged_in": rec["logged_in"], "num_compromised": 0,
        "root_shell": 0, "su_attempted": 0, "num_root": 0, "num_file_creations": 0, "num_shells": 0,
        "num_access_files": 0, "num_outbound_cmds": 0, "is_host_login": 0, "is_guest_login": 0,
        "count": count, "srv_count": srv_count,
        "serror_rate": rate(window, serr), "srv_serror_rate": rate(window_srv, serr),
        "rerror_rate": rate(window, rerr), "srv_rerror_rate": rate(window_srv, rerr),
        "same_srv_rate": round(srv_count / count, 4), "diff_srv_rate": round(1 - srv_count / count, 4),
        "srv_diff_host_rate": rate(window_srv, other_host),
        "dst_host_count": len(hosts), "dst_host_srv_count": len(hosts_srv),
        "dst_host_same_srv_rate": round(len(hosts_srv) / len(hosts), 4),
        "dst_host_diff_srv_rate": round(1 - len(hosts_srv) / len(hosts), 4),
        "dst_host_same_src_port_rate": rate(hosts, lambda r: r["src_port"] == rec["src_port"]),
        "dst_host_srv_diff_host_rate": rate(hosts_srv, other_host),
        "dst_host_serror_rate": rate(hosts, serr), "dst_host_srv_serror_rate": rate(hosts_srv, serr),
        "dst_host_rerror_rate": rate(hosts, rerr), "dst_host_srv_rerror_rate": rate(hosts_srv, rerr),
    }
    return {k: feats[k] for k in FEATURE_ORDER}


def finalize(flow, now):
    """Close a flow, build its features, and queue it for posting. Called with LOCK held."""
    FLOWS.pop(flow.key, None)
    CLOSED[flow.key] = now + CLOSED_MEMORY

    flag = tcp_flag(flow)
    rec = {
        "start": flow.start, "src_ip": flow.remote_ip, "src_port": flow.remote_port,
        "proto": flow.proto, "service": service_name(flow.proto, flow.local_port), "flag": flag,
        "duration": int(flow.end - flow.start), "src_bytes": flow.src_bytes, "dst_bytes": flow.dst_bytes,
        "urgent": flow.urgent, "wrong_fragment": flow.fragments,
        # simple guess: a completed web-style exchange with data both ways looks like a normal session
        "logged_in": 1 if (flow.proto == "tcp" and flag == "SF" and flow.src_bytes > 0 and flow.dst_bytes > 0) else 0,
    }
    HISTORY.append(rec)
    feats = compute_features(rec)

    STATS["flows"] += 1
    try:
        QUEUE.put_nowait((rec, feats))
    except queue.Full:
        STATS["dropped"] += 1     # the API cannot keep up (floods); features still counted in the windows


# ---------------------------------------------------------------- packets
def handle_packet(pkt):
    if IP not in pkt:
        return
    ip = pkt[IP]
    if ip.dst == LOCAL_IP:
        inbound, remote = True, ip.src
    elif ip.src == LOCAL_IP:
        inbound, remote = False, ip.dst
    else:
        return
    if remote == LOCAL_IP or remote in EXCLUDED:
        return

    now = time.time()
    payload = len(pkt[Raw].load) if Raw in pkt else 0
    fragment = 1 if (int(ip.flags) & 1 or ip.frag) else 0
    STATS["packets"] += 1

    if TCP in pkt:
        t = pkt[TCP]
        fl = int(t.flags)
        syn, ack, fin, rst, urg = bool(fl & 2), bool(fl & 16), bool(fl & 1), bool(fl & 4), bool(fl & 32)
        rport, lport = (t.sport, t.dport) if inbound else (t.dport, t.sport)
        key = (remote, int(rport), int(lport), "tcp")
        with LOCK:
            flow = FLOWS.get(key)
            if flow is None:
                if not inbound or CLOSED.get(key, 0) > now:
                    return                       # reply to a flow we never saw, or a late packet
                flow = Flow(key, now, remote, int(rport), int(lport), "tcp")
                FLOWS[key] = flow
            if not inbound and syn and ack and flow.synack:
                return                           # retransmitted SYN-ACK: do not stretch the flow
            flow.last = flow.end = now
            flow.fragments += fragment
            if inbound:
                flow.src_bytes += payload
                if syn and not ack:
                    flow.syn = True
                elif ack and not syn and flow.synack and not rst:
                    flow.ack_hs = True
                flow.fin_in |= fin
                flow.rst_in |= rst
                flow.urgent += 1 if urg else 0
            else:
                flow.dst_bytes += payload
                if syn and ack:
                    flow.synack = True
                flow.fin_out |= fin
                flow.rst_out |= rst
            if flow.rst_in or flow.rst_out or (flow.fin_in and flow.fin_out):
                finalize(flow, now)

    elif UDP in pkt:
        u = pkt[UDP]
        rport, lport = (u.sport, u.dport) if inbound else (u.dport, u.sport)
        key = (remote, int(rport), int(lport), "udp")
        with LOCK:
            flow = FLOWS.get(key)
            if flow is None:
                if not inbound or CLOSED.get(key, 0) > now:
                    return
                flow = Flow(key, now, remote, int(rport), int(lport), "udp")
                FLOWS[key] = flow
            flow.last = flow.end = now
            flow.fragments += fragment
            if inbound:
                flow.src_bytes += payload
            else:
                flow.dst_bytes += payload

    elif ICMP in pkt:
        ic = pkt[ICMP]
        if ic.type not in (0, 8):
            return
        key = (remote, int(ic.id), int(ic.seq), "icmp")
        with LOCK:
            flow = FLOWS.get(key)
            if flow is None:
                if not (inbound and ic.type == 8) or CLOSED.get(key, 0) > now:
                    return
                flow = Flow(key, now, remote, 0, 0, "icmp")
                FLOWS[key] = flow
            flow.last = flow.end = now
            if inbound:
                flow.src_bytes += payload
            else:
                flow.dst_bytes += payload
                finalize(flow, now)              # echo reply seen: the exchange is complete


def on_packet(pkt):
    try:
        handle_packet(pkt)
    except Exception as exc:                     # one odd packet must never stop the sensor
        STATS["errors"] += 1
        if STATS["errors"] <= 5:
            log(f"packet error: {exc!r}")


# ------------------------------------------------------------- background
def expiry_loop():
    """Close flows that have gone quiet."""
    while True:
        time.sleep(0.25)
        now = time.time()
        with LOCK:
            for flow in [f for f in FLOWS.values() if now - f.last >= FLOW_TIMEOUT]:
                finalize(flow, now)
            for key in [k for k, until in CLOSED.items() if until <= now]:
                del CLOSED[key]


def record_csv(rec, feats):
    new = not os.path.exists(RECORD_CSV) or os.path.getsize(RECORD_CSV) == 0
    with CSV_LOCK, open(RECORD_CSV, "a", newline="", encoding="utf8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["timestamp", "src_ip"] + FEATURE_ORDER)
        w.writerow([round(rec["start"], 3), rec["src_ip"]] + [feats[k] for k in FEATURE_ORDER])


def post_worker():
    session = requests.Session()
    shown = 0
    while True:
        rec, feats = QUEUE.get()
        if RECORD_CSV:
            try:
                record_csv(rec, feats)
            except OSError as exc:
                if STATS["csv_errors"] == 0:
                    log(f"cannot write {RECORD_CSV}: {exc}")
                STATS["csv_errors"] += 1
        if VERBOSE and STATS["verbose_shown"] < VERBOSE_LIMIT:
            STATS["verbose_shown"] += 1
            log("features " + json.dumps(feats))
        if DRY_RUN:
            continue
        body = {"sample": feats, "source_ip": rec["src_ip"], "instance_id": INSTANCE_ID, "service_id": SERVICE_ID}
        try:
            resp = session.post(f"{API_URL}/respond", json=body, timeout=30)
        except requests.RequestException as exc:
            STATS["post_errors"] += 1
            if STATS["post_errors"] <= 5:
                log(f"post failed: {exc}")
            continue
        if not resp.ok:
            STATS["post_errors"] += 1
            if STATS["post_errors"] <= 5:
                log(f"API returned {resp.status_code}: {resp.text[:300]}")
            continue
        r = resp.json()
        STATS["posted"] += 1
        STATS["class_" + r["predicted_class"]] += 1
        log(f"{rec['src_ip']}:{rec['src_port']} -> {rec['service']}/{rec['flag']} "
            f"src={rec['src_bytes']}B dst={rec['dst_bytes']}B | {r['predicted_class']} {r['confidence']:.2f} "
            f"risk={r['risk_level']} | action={r['action']} MTTD={r['mttd_ms']:.0f}ms MTTR={r['mttr_ms']:.0f}ms")


def stats_loop():
    last = collections.Counter()
    while True:
        time.sleep(5)
        with STATS_LOCK:
            snap = collections.Counter(STATS)
        classes = {k[6:]: v for k, v in snap.items() if k.startswith("class_")}
        log(f"STATS packets={snap['packets']} (+{snap['packets'] - last['packets']}) flows={snap['flows']} "
            f"posted={snap['posted']} dropped={snap['dropped']} queued={QUEUE.qsize()} "
            f"errors={snap['errors'] + snap['post_errors']} classes={classes}")
        last = snap


# ------------------------------------------------------------------ start
def wait_for_setup():
    global LOCAL_IP
    for _ in range(60):
        try:
            LOCAL_IP = get_if_addr(IFACE)
        except Exception:
            LOCAL_IP = "0.0.0.0"
        if LOCAL_IP != "0.0.0.0":
            break
        time.sleep(1)
    else:
        raise SystemExit(f"Interface {IFACE} has no IP address. Check SENSOR_IFACE (try eth0).")

    for host in EXCLUDE_HOSTS:
        try:
            EXCLUDED.add(socket.gethostbyname(host))
        except OSError:
            log(f"note: could not resolve {host}; its traffic will not be excluded")

    if not DRY_RUN:
        for _ in range(60):
            try:
                if requests.get(f"{API_URL}/health", timeout=3).ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(1)
        else:
            raise SystemExit(f"API not reachable at {API_URL}")


def main():
    wait_for_setup()
    log(f"sensor up: iface={IFACE} victim_ip={LOCAL_IP} excluded={sorted(EXCLUDED)} api={API_URL} "
        f"dry_run={DRY_RUN} timeout={FLOW_TIMEOUT}s record_csv={RECORD_CSV or 'off'}")
    for fn in [expiry_loop, stats_loop] + [post_worker] * POST_WORKERS:
        threading.Thread(target=fn, daemon=True).start()
    log("sniffing...")
    sniff(iface=IFACE, prn=on_packet, store=False)


if __name__ == "__main__":
    main()
