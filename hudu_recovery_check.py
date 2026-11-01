#!/usr/bin/env python3
"""Compare a Hudu source with an operator-restored test instance, read-only."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

PAGE_SIZE = 25
RESOURCES = {
    "companies": "companies",
    "assets": "assets",
    "articles": "articles",
    "procedures": "procedures",
}


class CheckError(Exception):
    """A safe-to-display error that never includes credentials or response bodies."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass
class HuduClient:
    base_url: str
    api_key: str

    @classmethod
    def create(cls, base_url: str, api_key: str) -> "HuduClient":
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise CheckError("Instance URL must be an absolute HTTP(S) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise CheckError("Instance URL must not include credentials, query, or fragment")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise CheckError("HTTP is allowed only for localhost; use HTTPS for instance URLs")
        return cls(base_url.rstrip("/"), api_key)

    @property
    def host(self) -> str:
        return urllib.parse.urlsplit(self.base_url).hostname or ""

    def get_json(self, path: str) -> object:
        url = f"{self.base_url}/api/v1/{path.lstrip('/')}"
        request = urllib.request.Request(
            url,
            headers={"x-api-key": self.api_key, "Accept": "application/json"},
            method="GET",
        )
        opener = urllib.request.build_opener(NoRedirect)
        try:
            with opener.open(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise CheckError(f"Hudu API returned HTTP {exc.code} for a read-only request") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise CheckError(f"Hudu API request failed ({type(exc).__name__})") from None

    def paged_records(self, endpoint: str) -> dict[str, object]:
        records: dict[str, object] = {}
        page = 1
        while True:
            payload = self.get_json(f"{endpoint}?page={page}")
            items = extract_records(payload, endpoint)
            for record in items:
                if not isinstance(record, dict) or "id" not in record:
                    raise CheckError(f"Unexpected {endpoint} response: record has no id")
                record_id = str(record["id"])
                if record_id in records:
                    raise CheckError(f"Unexpected {endpoint} response: duplicate record id")
                records[record_id] = record
            if len(items) < PAGE_SIZE:
                return records
            page += 1
            time.sleep(0.2)

    def uploads(self) -> dict[str, dict[str, object]]:
        payload = self.get_json("uploads")
        items = extract_records(payload, "uploads")
        uploads: dict[str, dict[str, object]] = {}
        for record in items:
            if not isinstance(record, dict) or "id" not in record:
                raise CheckError("Unexpected uploads response: record has no id")
            record_id = str(record["id"])
            if record_id in uploads:
                raise CheckError("Unexpected uploads response: duplicate upload id")
            uploads[record_id] = record
        return uploads

    def inventory(self) -> dict[str, object]:
        resources = {
            endpoint: sorted(self.paged_records(endpoint))
            for endpoint in RESOURCES
        }
        uploads = self.uploads()
        return {
            "resources": resources,
            "uploads": [
                {"id": upload_id, "size": record.get("size")}
                for upload_id, record in sorted(uploads.items())
            ],
        }


def extract_records(payload: object, key: str) -> list[object]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        value = payload.get("data")
        if isinstance(value, list):
            return value
    raise CheckError(f"Unexpected {key} response: expected a record list")


def check_file_url(url: str, allowed_hosts: set[str]) -> tuple[bool, str, int | None]:
    """HEAD-check an upload without sending the Hudu API key to file storage."""
    current = url
    for _ in range(4):
        parsed = urllib.parse.urlsplit(current)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host or host not in allowed_hosts:
            return False, "host_not_allowed", None
        if parsed.username or parsed.password or parsed.fragment:
            return False, "invalid_file_url", None
        request = urllib.request.Request(current, method="HEAD")
        opener = urllib.request.build_opener(NoRedirect)
        try:
            with opener.open(request, timeout=20) as response:
                return response.status == 200, "ok" if response.status == 200 else "http_error", response.headers.get("Content-Length")
        except urllib.error.HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                location = exc.headers.get("Location")
                if not location:
                    return False, "redirect_without_location", None
                current = urllib.parse.urljoin(current, location)
                continue
            return False, f"http_{exc.code}", None
        except (urllib.error.URLError, TimeoutError):
            return False, "connection_error", None
    return False, "too_many_redirects", None


def compare_resources(source: HuduClient, restored: HuduClient) -> list[tuple[str, int, int, int]]:
    results = []
    for endpoint, label in RESOURCES.items():
        source_ids = source.paged_records(endpoint)
        restored_ids = restored.paged_records(endpoint)
        missing = len(source_ids.keys() - restored_ids.keys())
        results.append((label, len(source_ids), len(restored_ids), missing))
    return results


def compare_uploads(source: HuduClient, restored: HuduClient, check_files: bool, extra_hosts: set[str]):
    original = source.uploads()
    recovered = restored.uploads()
    missing = len(original.keys() - recovered.keys())
    size_mismatch = 0
    for upload_id in original.keys() & recovered.keys():
        source_size = original[upload_id].get("size")
        target_size = recovered[upload_id].get("size")
        if source_size is not None and target_size is not None and str(source_size) != str(target_size):
            size_mismatch += 1

    files_ok = files_failed = files_unknown = 0
    if check_files:
        allowed_hosts = {source.host.lower(), restored.host.lower(), *extra_hosts}
        for record in recovered.values():
            url = record.get("url")
            if not isinstance(url, str):
                files_unknown += 1
                continue
            ok, reason, content_length = check_file_url(url, allowed_hosts)
            if not ok:
                files_failed += 1
                continue
            expected_size = record.get("size")
            if content_length is not None and expected_size is not None and str(content_length) != str(expected_size):
                files_failed += 1
            else:
                files_ok += 1
            time.sleep(0.2)
    return len(original), len(recovered), missing, size_mismatch, files_ok, files_failed, files_unknown


def capture_manifest(client: HuduClient, output: pathlib.Path) -> None:
    payload = {
        "schema_version": 1,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        **client.inventory(),
    }
    try:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
    except FileExistsError:
        raise
    except OSError:
        raise CheckError("Could not create baseline manifest") from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            output.unlink()
        except OSError:
            pass
        raise CheckError("Could not write baseline manifest") from None


def read_manifest(path: pathlib.Path) -> dict[str, object]:
    try:
        with path.open(encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError):
        raise CheckError("Could not read baseline manifest") from None
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise CheckError("Unsupported baseline manifest")
    resources = data.get("resources")
    uploads = data.get("uploads")
    if not isinstance(resources, dict) or not isinstance(uploads, list):
        raise CheckError("Invalid baseline manifest")
    for endpoint in RESOURCES:
        ids = resources.get(endpoint)
        if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
            raise CheckError("Invalid baseline resource inventory")
    if any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in uploads):
        raise CheckError("Invalid baseline upload inventory")
    return data


def compare_manifest(baseline: dict[str, object], restored: HuduClient, check_files: bool, extra_hosts: set[str]):
    live_resources = {
        endpoint: sorted(restored.paged_records(endpoint))
        for endpoint in RESOURCES
    }
    live_uploads = restored.uploads()
    base_resources = baseline["resources"]
    results = []
    for endpoint, label in RESOURCES.items():
        old_ids = set(base_resources[endpoint])
        new_ids = set(live_resources[endpoint])
        results.append((label, len(old_ids), len(new_ids), len(old_ids - new_ids)))

    old_uploads = {record["id"]: record for record in baseline["uploads"]}
    new_uploads = live_uploads
    missing = len(old_uploads.keys() - new_uploads.keys())
    size_mismatch = sum(
        old_uploads[upload_id].get("size") is not None
        and new_uploads[upload_id].get("size") is not None
        and str(old_uploads[upload_id]["size"]) != str(new_uploads[upload_id]["size"])
        for upload_id in old_uploads.keys() & new_uploads.keys()
    )
    files_ok = files_failed = files_unknown = 0
    if check_files:
        allowed_hosts = {restored.host.lower(), *extra_hosts}
        for upload_id in old_uploads.keys() & new_uploads.keys():
            record = new_uploads[upload_id]
            url = record.get("url")
            if not isinstance(url, str):
                files_unknown += 1
                continue
            ok, _, content_length = check_file_url(url, allowed_hosts)
            if not ok:
                files_failed += 1
            elif (
                content_length is not None
                and record.get("size") is not None
                and str(content_length) != str(record["size"])
            ):
                files_failed += 1
            else:
                files_ok += 1
            time.sleep(0.2)
    return results, (len(old_uploads), len(new_uploads), missing, size_mismatch, files_ok, files_failed, files_unknown)


def print_results(results, uploads, check_files: bool) -> int:
    print("Hudu recovery comparison (record IDs and counts only)")
    print(f"{'Resource':<12} {'Baseline':>9} {'Restored':>10} {'Missing':>9}")
    failed = False
    for label, baseline_count, restored_count, missing in results:
        print(f"{label:<12} {baseline_count:>9} {restored_count:>10} {missing:>9}")
        failed |= missing > 0
    baseline_count, restored_count, missing, size_mismatch, files_ok, files_failed, files_unknown = uploads
    print(f"{'uploads':<12} {baseline_count:>9} {restored_count:>10} {missing:>9}")
    print(f"Upload size mismatches: {size_mismatch}")
    failed |= missing > 0 or size_mismatch > 0
    if check_files:
        print(f"Upload URLs reachable: {files_ok}; unavailable: {files_failed}; unknown: {files_unknown}")
        failed |= files_failed > 0 or files_unknown > 0
    else:
        print("Upload URLs were not checked; file contents are never downloaded.")
    print("RESULT: FAIL" if failed else "RESULT: PASS (checked inventory only)")
    return 1 if failed else 0


def new_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Compare a Hudu baseline with an operator-restored test instance")
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture", help="Capture record IDs and upload sizes before a recovery drill")
    capture.add_argument("--url", required=True, help="Source Hudu instance URL")
    capture.add_argument("--output", required=True, type=pathlib.Path, help="New local baseline file (will not overwrite)")
    compare = subparsers.add_parser("compare", help="Compare a baseline with a restored Hudu instance")
    compare.add_argument("--url", required=True, help="Restored, separately licensed test instance URL")
    compare.add_argument("--baseline", required=True, type=pathlib.Path)
    compare.add_argument("--check-files", action="store_true", help="HEAD-check restored upload URLs")
    compare.add_argument("--allow-media-host", action="append", default=[], help="Explicit HTTPS hostname allowed for upload URLs or redirects")
    args = parser.parse_args(argv)
    api_key = os.environ.get("HUDU_API_KEY")
    if not api_key:
        parser.error("Set HUDU_API_KEY in the environment; it is never stored in the baseline")
    try:
        client = HuduClient.create(args.url, api_key)
        if args.command == "capture":
            capture_manifest(client, args.output)
            print(f"Baseline captured ({args.output.stat().st_size} bytes, mode 0600). Store it with the corresponding recovery point.")
            return 0
        baseline = read_manifest(args.baseline)
        results, uploads = compare_manifest(
            baseline,
            client,
            args.check_files,
            {host.lower() for host in args.allow_media_host},
        )
        return print_results(results, uploads, args.check_files)
    except CheckError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except FileExistsError:
        print("ERROR: baseline output already exists; choose a new path", file=sys.stderr)
        return 2


def legacy_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare source and restored Hudu data using read-only API calls")
    parser.add_argument("--source-url", required=True, help="Source Hudu instance URL")
    parser.add_argument("--restored-url", required=True, help="Operator-restored, separately licensed test instance URL")
    parser.add_argument("--check-files", action="store_true", help="HEAD-check restored upload URLs; no file contents are downloaded")
    parser.add_argument("--allow-media-host", action="append", default=[], help="Explicit HTTPS hostname allowed for an upload URL or redirect")
    args = parser.parse_args(argv)

    source_key = os.environ.get("HUDU_SOURCE_API_KEY")
    restored_key = os.environ.get("HUDU_RESTORED_API_KEY")
    if not source_key or not restored_key:
        parser.error("Set HUDU_SOURCE_API_KEY and HUDU_RESTORED_API_KEY in the environment")

    try:
        source = HuduClient.create(args.source_url, source_key)
        restored = HuduClient.create(args.restored_url, restored_key)
        results = compare_resources(source, restored)
        uploads = compare_uploads(source, restored, args.check_files, {host.lower() for host in args.allow_media_host})
    except CheckError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print("Hudu recovery comparison (record IDs and counts only)")
    print(f"{'Resource':<12} {'Source':>8} {'Restored':>10} {'Missing':>9}")
    failed = False
    for label, source_count, restored_count, missing in results:
        print(f"{label:<12} {source_count:>8} {restored_count:>10} {missing:>9}")
        failed |= missing > 0
    source_count, restored_count, missing, size_mismatch, files_ok, files_failed, files_unknown = uploads
    print(f"{'uploads':<12} {source_count:>8} {restored_count:>10} {missing:>9}")
    print(f"Upload size mismatches: {size_mismatch}")
    if args.check_files:
        print(f"Upload URLs reachable: {files_ok}; unavailable: {files_failed}; unknown: {files_unknown}")
        failed |= files_failed > 0 or files_unknown > 0
    else:
        print("Upload file contents were not checked; rerun with --check-files to HEAD-check the restored URLs.")
    failed |= missing > 0 or size_mismatch > 0
    print("RESULT: FAIL" if failed else "RESULT: PASS (API inventory only)")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "legacy":
        return legacy_main(arguments[1:])
    if arguments and arguments[0] in {"capture", "compare", "--help", "-h"}:
        return new_main(arguments)
    return legacy_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
