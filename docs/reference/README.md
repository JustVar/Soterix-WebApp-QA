# Reference Documentation

This folder contains platform, hardware, and methodology documentation for reference during test development.

## Hardware Documentation

Location: `docs/reference/hardware/`

| File | Description |
|------|-------------|
| Hardware_Platform_Presentation.docx | Overview of NexaiQ hardware platform architecture |
| HW_Enablement_Documentation_v2.docx | Hardware setup and enablement procedures |
| HW_Discussion_Flow.docx | Hardware discussion and decision flow diagrams |
| NexaiQ_ZFS_RAID_REQ2025.docx | ZFS RAID requirements and specifications for 2025 |
| OEM_OS_Installation_-_Quick_Start_Guide.docx | Ubuntu OS and application installation guide |
| OpenZFS_for_NexaiQ.docx | OpenZFS storage configuration for NexaiQ |

## Archive (Original Methodology Docs)

Location: `docs/reference/archive/`

| File | Description |
|------|-------------|
| Optimized_Triple-Helix_Testing.txt | Original Triple-Helix methodology document |
| v1_Helix_QA.pdf | Earlier version of Triple-Helix QA methodology |

These have been merged into `docs/TRIPLE_HELIX_METHODOLOGY.md`

## Usage

These documents help QA understand:
- How edge boxes are installed and configured
- RAID and storage requirements
- Hardware testing requirements
- Platform architecture
- Testing methodology and quality gates

## Updating

When PM provides updated documentation, replace the relevant file and update this README.

## Note on Word Documents

`.docx` files cannot be analyzed inline by most automation tools. For content analysis:
- Convert to markdown for version-controlled content
- Or extract text via `python-docx` / `pandoc` before processing
