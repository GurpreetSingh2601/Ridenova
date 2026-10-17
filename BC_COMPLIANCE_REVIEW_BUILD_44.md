# BC compliance review — not operating approval

This release implements upload/review history, expiry enforcement and configurable requirements, not document authenticity checks or legal certification. The existing four staging requirements remain; authorized staff can additionally require RCC, driving record and criminal-record check after review.

A qualified reviewer must confirm current commercial licence requirements, driving/police checks, RCC contents/expiry, vehicle eligibility/inspections, commercial insurance, company transportation/safety licences, identifiers, daily inspections, required document availability, accessibility, privacy, worker protections and provincial reporting. An approved upload does not authorize commercial operation.

Official sources consulted during development:
- https://www2.gov.bc.ca/gov/content?id=574A0AB5CE254371938E68995916DF4F
- https://www2.gov.bc.ca/gov/content/transportation/vehicle-safety-enforcement/services/passenger-transportation/guidance-resources/required-documents/record-check-certificates
- https://www2.gov.bc.ca/gov/content/transportation/vehicle-safety-enforcement/services/passenger-transportation/transportation-network-services/tns-enforcement
- https://www2.gov.bc.ca/assets/gov/driving-and-transportation/cvse/passenger-transportation/industry-notices/pt-bulletin-01-2026-record-check-certificate-process.pdf

The 2026 bulletin search summary reports changed RCC expiry rules while an older overview describes the previous rule. Full bulletin retrieval was unavailable here. Do not hard-code an expiry term from the older page. A qualified reviewer must establish the current requirement; this build uses explicitly entered expiry dates in America/Vancouver.
