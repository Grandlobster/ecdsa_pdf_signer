"""
activity_log.py

Remembers how many documents were signed and verified, and keeps a short
list of recent activity for the dashboard. It is saved in data/activity_log.json.
No document contents are stored, only file names and short results.
"""

import datetime
import json
import os

import folders


MAXIMUM_STORED_ENTRIES = 200


def build_log_path():
    return os.path.join(folders.DATA_FOLDER, "activity_log.json")


def create_empty_log():
    empty_log = {
        "signed_total": 0,
        "verified_total": 0,
        "entries": [],
    }

    return empty_log


def read_log():
    # Read the log file. A missing or damaged file simply means "no activity yet".
    log_path = build_log_path()

    if not os.path.exists(log_path):
        return create_empty_log()

    try:
        with open(log_path, "r", encoding="utf-8") as log_file:
            log = json.load(log_file)
    except (OSError, ValueError):
        return create_empty_log()

    if not isinstance(log, dict) or "entries" not in log:
        return create_empty_log()

    return log


def write_log(log):
    # Write to a temporary file first, then swap it in, so a crash
    # in the middle of writing can never leave a half-written log.
    folders.make_sure_folders_exist()

    log_path = build_log_path()
    temporary_path = log_path + ".tmp"

    with open(temporary_path, "w", encoding="utf-8") as log_file:
        json.dump(log, log_file, indent=2)

    os.replace(temporary_path, log_path)


def add_activity(kind, filename, result_text, signed_file_name=None):
    # Add one entry. "kind" is either "sign" or "verify".
    log = read_log()

    now = datetime.datetime.now(datetime.timezone.utc)

    entry = {
        "kind": kind,
        "filename": filename,
        "result": result_text,
        "signed_file_name": signed_file_name,
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # The newest entry goes first.
    log["entries"].insert(0, entry)
    log["entries"] = log["entries"][:MAXIMUM_STORED_ENTRIES]

    if kind == "sign":
        log["signed_total"] = log.get("signed_total", 0) + 1

    if kind == "verify":
        log["verified_total"] = log.get("verified_total", 0) + 1

    write_log(log)


def get_activity_summary(recent_count):
    # Return the totals and the most recent entries for the dashboard.
    log = read_log()

    summary = {
        "signed_total": log.get("signed_total", 0),
        "verified_total": log.get("verified_total", 0),
        "recent": log["entries"][:recent_count],
    }

    return summary
