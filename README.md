# Hudu Recovery Check

Local-only CLI for comparing a small baseline from self-hosted Hudu with a restored, separately licensed test instance. It uses read-only API requests and checks companies, assets, articles, procedures, and upload metadata. Optional `--check-files` sends HEAD requests to restored upload URLs; it does not download file contents.

Hudu's recovery guide says a complete backup needs both PostgreSQL and uploaded files. It also warns that its backup hash check does not prove that the application restores, and recommends periodic restore tests. This tool helps compare the result of a restore. It does not create backups, restore the instance, or prove file contents are intact. [Hudu recovery guide](https://support.hudu.com/hc/en-us/articles/11653994397079-Self-Hosted-Backups-and-Restores)

## Requirements

- Python 3.11+
- Two reachable Hudu instances: the source and a test instance that you are authorized and licensed to run
- Read-only Hudu API keys; disable destructive actions and password access

Hudu exposes detailed API documentation inside each instance. Check the resource names and response schema for your installed Hudu version before relying on a report. The public API guide documents `x-api-key` authentication, pagination, rate limits, and least-privilege API key configuration. [Hudu REST API guidance](https://support.hudu.com/hc/en-us/articles/11422780787735-REST-API)

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
  --check-files
```

If uploaded-file URLs redirect to a separate storage hostname, allow it explicitly:

```sh
python3 hudu_recovery_check.py compare \
  --url https://hudu-recovery-test.example.com \
  --baseline hudu-baseline.json \
  --check-files \
  --allow-media-host files.example.net
```

Never put real keys in shell history, command-line arguments, logs, or this repository. The CLI prints counts and status only; it does not save API responses or forward API keys to upload hosts. The baseline stores record IDs and upload sizes, not names, passwords, or file contents. It is created with mode `0600` and will not overwrite an existing file. Use HTTPS except for localhost. The CLI follows upload URL redirects only when every hostname is explicitly allowed or matches the restored Hudu host.

## Current limits

- The CLI compares IDs in the captured inventory, upload metadata, and optionally whether each restored upload URL responds to `HEAD` with a matching content length. It does not hash or download file contents, validate password values, compare document bodies, or verify every Hudu feature.
- If source data changes between baseline capture and backup, the baseline can include records absent from that recovery point; capture during a stable backup window.
- A PASS means the checked API inventories match; it is not certification or proof of a complete disaster recovery.
- This is a prototype. API response shapes and upload URL behavior must be checked against each deployed Hudu version. A HEAD request may be unsupported by a storage provider.
- The paid path under investigation is recurring recovery-drill reporting and support for MSPs. There is no customer or revenue validation yet.

## License

MIT. See [LICENSE](LICENSE).
