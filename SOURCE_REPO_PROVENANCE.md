# Source Repository Provenance

Current local full working commit before clean snapshot:
232f5cfc12cb7f2b90d29a6dd827cc13fac7cc48

Remote pre-clean snapshot commit:
998f6af90cafa3cadbd61e58c84ddf45733cdd8a

Reason for clean orphan snapshot:
Direct push and force-with-lease push from the inherited branch failed because GitHub returned HTTP 500 during LFS upload attempts. The clean snapshot avoids inherited heavy history and LFS objects while preserving the final HackAIthon MVP working tree needed for product development.
