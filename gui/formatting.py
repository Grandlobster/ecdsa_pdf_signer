"""
formatting.py

Small helpers that turn raw values into readable text.
"""

import datetime


def format_bytes(byte_count):
    # 1536 becomes "1.5 KB".
    if byte_count < 1024:
        return str(byte_count) + " bytes"

    if byte_count < 1024 * 1024:
        return "%.1f KB" % (byte_count / 1024)

    return "%.2f MB" % (byte_count / (1024 * 1024))


def parse_time_text(time_text):
    # Turn text like "2026-11-17T09:30:00Z" or an ISO time with offset into a datetime.
    if not time_text:
        return None

    cleaned_text = time_text.replace("Z", "+00:00")

    try:
        return datetime.datetime.fromisoformat(cleaned_text)
    except ValueError:
        return None


def format_date_time(time_text):
    # Show a time in the local time zone of this computer.
    moment = parse_time_text(time_text)

    if moment is None:
        return "Not available"

    if moment.tzinfo is not None:
        moment = moment.astimezone()

    return moment.strftime("%d %b %Y, %H:%M")


def format_date(time_text):
    moment = parse_time_text(time_text)

    if moment is None:
        return "Not available"

    if moment.tzinfo is not None:
        moment = moment.astimezone()

    return moment.strftime("%d %b %Y")


def short_fingerprint(fingerprint_text):
    # "DB:1F:13:5A:...:83:17" becomes "DB:1F:13:5A ... 83:17".
    byte_list = fingerprint_text.split(":")

    if len(byte_list) <= 8:
        return fingerprint_text

    first_part = ":".join(byte_list[:4])
    last_part = ":".join(byte_list[-2:])

    return first_part + " ... " + last_part


def split_fingerprint_in_two_lines(fingerprint_text):
    # A SHA-256 fingerprint has 32 bytes. Two lines of 16 fit nicely on screen.
    byte_list = fingerprint_text.split(":")
    first_line = ":".join(byte_list[:16])
    second_line = ":".join(byte_list[16:])

    return first_line + "\n" + second_line


def describe_validity(certificate):
    # One short sentence about the validity of a certificate.
    if certificate["is_currently_valid"]:
        return "Valid today, " + str(certificate["days_remaining"]) + " days remaining"

    if certificate["days_remaining"] < 0:
        return "Expired"

    return "Not valid yet"
