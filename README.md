# Hudu Recovery Check

Local-only CLI for comparing a small baseline from self-hosted Hudu with a restored, separately licensed test instance. It uses read-only API requests and checks companies, assets, articles, procedures, and upload metadata. Optional `--check-files` sends HEAD requests to restored upload URLs; it does not download file contents.

Hudu's recovery guide says a complete backup needs both PostgreSQL and uploaded files. It also warns that its backup hash check does not prove that the application restores, and recommends periodic restore tests. This tool helps compare the result of a restore. It does not create backups, restore the instance, or prove file contents are intact. [Hudu recovery guide](https://support.hudu.com/hc/en-us/articles/11653994397079-Self-Hosted-Backups-and-Restores)

## Requirements

- Python 3.11+
- Two reachable Hudu instances: the source and a test instance that you are authorized and licensed to run
- A dedicated Hudu API key with password access, destructive actions, and export permission disabled where possible

The CLI sends only `GET` requests, but Hudu does not document a method-level GET-only key setting. Treat its dedicated API key as privileged and restrict allowed IPs and company scope where practical. Company-scoped keys only see scoped records, so use an unscoped key when you intend to compare the full instance. Hudu exposes detailed API documentation inside each instance; check the installed version's schema before relying on a report. [Hudu REST API guidance](https://support.hudu.com/hc/en-us/articles/11422780787735-REST-API)

**Terms check required:** Hudu's current [Terms of Service](https://www.hudu.com/terms-of-service) broadly restrict automated access, while its API guide describes automation use. The public docs do not settle whether this third-party CLI workflow is permitted under your agreement. Confirm with Hudu before running it on a licensed instance or offering recurring/hosted drills. This tool is local and operator-initiated, but that does not by itself resolve the terms question.

## Suggested drill procedure

1. Confirm the recovery target is a separately licensed test instance and that no production DNS or mail routes point to it.
2. Pause Hudu changes, capture the baseline, then take the database and uploaded-file backup as one recovery point.
3. Restore both the PostgreSQL database and uploaded files to the test instance using Hudu's documented procedure.
4. Run the comparison from this tool. Investigate missing IDs, upload size mismatches, and unreachable upload URLs before marking the drill successful.
5. Manually open a small, representative sample of restored records and attachments in the Hudu UI. This CLI cannot verify document contents, password values, permissions, or application behavior.
6. Record the backup timestamp, Hudu version, restore duration, findings, and corrective actions in your incident or change log; then remove the test environment according to your retention policy.

Do not expose the restored instance publicly during a drill. Use access controls comparable to production because restored data may contain sensitive information.

## Run a recovery check

Capture an inventory close to the backup checkpoint while Hudu data is not changing. The baseline contains record IDs and upload sizes only. Store it securely with that recovery point.

```sh
read -rsp 'Source Hudu API key: ' HUDU_API_KEY
printf '\n'
export HUDU_API_KEY
python3 hudu_recovery_check.py capture \
  --url https://hudu.example.com \
  --output hudu-baseline.json
```

After restoring the Hudu backup into a separate test instance, use a read-only key for that instance:

```sh
read -rsp 'Restored test API key: ' HUDU_API_KEY
printf '\n'
export HUDU_API_KEY
python3 hudu_recovery_check.py compare \
  --url https://hudu-recovery-test.example.com \
  --baseline hudu-baseline.json \
  --check-files \
  --report recovery-report.json
```

If uploaded-file URLs redirect to a separate storage hostname, allow it explicitly:

```sh
python3 hudu_recovery_check.py compare \
  --url https://hudu-recovery-test.example.com \
  --baseline hudu-baseline.json \
  --check-files \
  --allow-media-host files.example.net
```

Never put real keys in shell history, command-line arguments, logs, or this repository. The CLI does not save API responses or forward API keys to upload hosts. The baseline stores record IDs and upload sizes, not names, passwords, or file contents. The optional JSON report contains counts and timestamps only; both files are created with mode `0600` and will not overwrite existing files. Use HTTPS except for localhost. The CLI follows upload URL redirects only when every hostname is explicitly allowed or matches the restored Hudu host.

## Current limits

- The CLI compares IDs in the captured inventory, upload metadata, and optionally whether each restored upload URL responds to `HEAD` with a matching content length. It does not hash or download file contents, validate password values, compare document bodies, or verify every Hudu feature.
- If source data changes between baseline capture and backup, the baseline can include records absent from that recovery point; capture during a stable backup window.
- A PASS means the checked API inventories match; it is not certification or proof of a complete disaster recovery.
- The optional JSON report is an inventory comparison artifact, not a restore certificate or customer attestation.
- This is a prototype. API response shapes and upload URL behavior must be checked against each deployed Hudu version. A HEAD request may be unsupported by a storage provider.

## Business hypothesis

The open-source CLI is intended to complement backup history products: it compares a pre-backup inventory with an operator-restored Hudu instance and creates a count-only report. A possible paid service is setup help and recurring, supervised restore drills with evidence reports for MSPs that manage multiple Hudu environments. This model is unvalidated; there are no customer interviews, paid pilots, or revenue yet. Do not treat this prototype as a managed backup service or a restore certificate.

See [market research and open questions](docs/MARKET_RESEARCH.md) for the current evidence, competing products, and validation gaps.

## License

MIT. See [LICENSE](LICENSE).
