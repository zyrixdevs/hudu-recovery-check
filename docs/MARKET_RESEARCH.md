# Market research and open questions

Research snapshot: 2026-11-01. This is public-source desk research, not customer validation.

## Documented problem

Hudu's self-hosted recovery guide says a complete backup requires both its PostgreSQL database and uploaded files. A database-only restore can leave broken images and missing attachments. Hudu explains that Doubletake's dump hash check proves the backup file is unchanged, not that a restored Hudu application is usable; it recommends recurring restores into a separate non-production environment and manual spot checks of records, passwords, and attachments. See [Hudu's backup and restore guide](https://support.hudu.com/hc/en-us/articles/11653994397079-Self-Hosted-Backups-and-Restores).

## Existing alternatives

- **Hudu Doubletake and operator-run test restores:** first-party backup tooling and documentation cover dump integrity and manual restore procedures. The documented full check still requires an operator to restore and inspect a separate environment.
- **RMMBackup:** its Hudu integration keeps a history of supported records and can include selected password and file collections. Its documentation describes snapshots and ZIP exports; RMMBackup says it does not restore captured data back into vendor platforms. It does not claim to validate a complete, running self-hosted Hudu restore. Full Access is currently described as free during open beta, so its future Hudu pricing is not established. [Hudu integration](https://rmmbackup.com/integrations/hudu) · [Hudu backup guide](https://rmmbackup.com/docs/how-to-back-up-hudu) · [product limitation](https://rmmbackup.com/)
- **MSP hosting and migration providers:** Rising Tide lists managed Hudu hosting with daily database backups at $175+/month, file backup as a $50/month add-on, and migration projects at $1,400 that include post-migration testing. These are adjacent services and prices, not evidence that MSPs will pay for recurring Hudu restore drills. [Rising Tide Hudu services](https://www.risingtidegroup.net/solutions/hudu-documentation)

## Licensing and product constraint

Hudu's current [Terms of Service](https://www.hudu.com/terms-of-service) define a self-hosted instance as licensed software and broadly restrict accessing or using it through bots or other automated methods. Hudu's [REST API guide](https://support.hudu.com/hc/en-us/articles/11422780787735-REST-API) says the API can automate documentation processes. These public sources do not settle whether a customer-run recovery-check CLI or a paid recurring drill service is permitted under a particular customer's agreement. This project does not make that legal determination. Before pilots or a hosted/managed offering, get written clarification from Hudu and require each operator to use an instance and API key they are authorized to use.

The prototype is local and user-initiated: it sends GET requests only when an operator runs it, stores no API key or response body, and does not provide an unattended service. That limits data exposure but does not itself resolve the terms question.

## Workflow signals

- In an MSP discussion about restore frequency, operators describe periodic random file and VM restores, including quarterly tests, and some report spending time checking backups. This supports a broader recurring restore-testing workflow, not Hudu-specific purchasing intent. [r/msp discussion](https://www.reddit.com/r/msp/comments/1jklgq5/how_often_do_you_actually_restore_anything_from/)
- A Hudu user describes protecting a self-hosted installation with Veeam and testing a restore to spare Hyper-V hardware. That is a concrete manual workaround, but one post cannot establish demand or willingness to pay. [r/hudu discussion](https://www.reddit.com/r/hudu/comments/n20lc3)

## Product wedge to test

The project currently captures a count-only inventory, compares it with an operator-restored instance, checks optional upload URL reachability, and writes a local report. The possible differentiator is a repeatable, isolated restore drill with operator-ready evidence across an MSP's Hudu environments. This CLI does not orchestrate backup creation or restoration and does not certify the full application.

## Paid-path hypothesis

Keep the local CLI open source. Test whether MSPs will pay for setup and recurring supervised restore drills, with scheduled evidence reports and retention for multiple client environments. Do not build hosted orchestration or set pricing until operators confirm that they have this recurring task, lack a satisfactory existing workflow, can use a licensed test environment, and would pay for help or evidence.

## What remains unproven

- No customer interviews, pilot users, purchase commitments, or revenue.
- No estimate of the number of MSPs that self-host Hudu and lack an adequate restore workflow.
- No live validation of this CLI against a real Hudu version; API schemas and upload URL behavior can vary by instance.
- No confirmation of Hudu licensing terms for automated or recurring throwaway instances.
- No written confirmation that Hudu permits third-party automated API use for this recovery-drill workflow under current customer terms.
- No evidence yet that a JSON inventory report is sufficient evidence for an MSP's audit or client needs.

## Suggested validation gate

Before investing in hosted scheduling or automated restore orchestration, seek five MSP interviews, two supervised pilot drills using environments each MSP is authorized to run, and at least one explicit paid pilot commitment. These are proposed decision thresholds, not achieved results.
