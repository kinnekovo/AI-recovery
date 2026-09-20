# Product Specification Changelog

Product specifications in this directory are immutable, versioned product inputs. Material changes require a new versioned document and a corresponding entry here; they must not be applied by silently rewriting a published specification.

## 2026-09-20

- Established `Speech_Rehab_Product_Design_v1.md` as the canonical Product Design v1 specification.
- Established `Speech_Rehab_UI_Interaction_Spec_v1.md` as the canonical UI / Interaction Spec v1 specification.
- Completed Product Reset v1 implementation against these two specifications, including additive migration `0040_product_reset_v1`, the patient and therapist vertical slices, seeded PostgreSQL acceptance, and regression/build/browser verification.
