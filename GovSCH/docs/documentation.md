# GovSCH Schema Documentation

This document provides a detailed breakdown of the **Executive Orders Schema**, **Framework Schema**, and **Regulations Schema** used in the GovSCH project.

## Executive Orders Schema (eoschema)

### Top-Level Fields
- **metadata** *(object, required)*  
  - `title`: Full title of the Executive Order.  
  - `number`: EO number (e.g., "14028").  
  - `date_signed`: Date of signing (ISO 8601).  
  - `issuing_authority`: The issuing authority (e.g., "President of the United States").  
  - `location`: Location of signing (e.g., "The White House").

- **preamble** *(object, required)*  
  - `authority_statement`: Legal authority for issuing the EO.  
  - `introductory_text`: Contextual preamble describing intent.

- **purpose** *(object, required)*  
  - `statement`: Policy goals and objectives of the EO.

- **policy** *(object, required)*  
  - `statement`: Overarching policy declaration.

- **definitions** *(array, optional)*  
  - Array of objects defining key terms used in the EO.

- **sections** *(array, required)*  
  - `section_number`: Section identifier.  
  - `section_title`: Section heading.  
  - `directives`: Array of actionable items within the section.  
    - `subsection_number`: Subsection identifier.  
    - `text`: Directive text.  
    - `responsible_entities`: Agencies or bodies assigned to act.  
    - `deadlines`: Associated deadline (ISO 8601).

- **implementation** *(object, optional)*  
  - `instructions`: Guidance for execution.  
  - `agency_roles`: Agencies involved in implementation.

- **general_provisions** *(object, optional)*  
  - `legal_authority`: Legal basis.  
  - `non_impairment_clause`: Clause protecting agency authorities.  
  - `enforceability_clause`: Limitations on enforceability.

- **closing** *(object, required)*  
  - `president_name`: Name of the issuing President.  
  - `date`: Date of issuance.

## Framework Schema (frameworkschema)

### Top-Level Fields
- **FrontMatter** *(object, required)*  
  - `TitleAndVersion`: Framework title and version.  
  - `Purpose`: Framework objectives.  
  - `ScopeAndApplicability`: Who the framework applies to.  
  - `Audience`: Intended users.  
  - `DocumentGovernance`: Version history and update process.

- **FrameworkOverview** *(object, required)*  
  - `ConceptualModel`: Overview of the framework approach.  
  - `PrinciplesAndObjectives`: Guiding principles.  
  - `IntegrationPoints`: Related frameworks, standards, and laws.

- **CoreProcess** *(array, required)*  
  - `StepName`: Name of the framework step.  
  - `Purpose`: Step objectives.  
  - `ExpectedOutcomes`: Deliverables or success criteria.  
  - `Tasks`: Array of tasks for the step.  
    - `TaskID`: Identifier.  
    - `TaskName`: Task title.  
    - `Inputs`: Inputs required.  
    - `Outputs`: Outputs produced.  
    - `RolesAndResponsibilities`: Primary and supporting roles.  
    - `Discussion`: Notes or considerations.

- **GovernanceAndOversight** *(object, optional)*  
  - `Roles`: Roles involved in oversight.  
  - `DecisionMakingStructure`: Governance hierarchy.  
  - `EscalationAndReporting`: Reporting obligations.

- **SupportingToolsAndArtifacts** *(object, optional)*  
  - `Deliverables`: Required artifacts.  
  - `Templates`: Provided templates.  
  - `ChecklistsAndReviews`: Review aids.

- **Appendices** *(object, optional)*  
  - `Glossary`: Definitions of framework terms.  
  - `Acronyms`: Acronym list.  
  - `References`: Cited works.  
  - `TaskSummaries`: Summary of tasks by step.  
  - `RoleDescriptions`: Detailed descriptions of roles.

---

## Regulations Schema (regschema)

### Top-Level Fields
- **Title** *(object, required)*  
  - `FullName`: Full name of the regulation.  
  - `ShortTitle`: Commonly used short title.

- **Preamble** *(object, required)*  
  - `ConstitutionalAuthority`: Legal authority or basis.  
  - `PurposeAndObjectives`: Purpose and goals.  
  - `ContextualJustification`: Historical or social rationale.

- **PreliminaryProvisions** *(object, required)*  
  - `Scope`:  
    - `TerritorialScope`: Geographic reach.  
    - `MaterialScope`: Activities covered.  
    - `Exemptions`: Exclusions.  
  - `Definitions`:  
    - `KeyTerms`: Definitions of terms.  
    - `InterpretiveProvisions`: Additional interpretive clauses.

- **Principles** *(array, required)*  
  - Core principles (e.g., lawfulness, fairness).

- **LawfulProcessing** *(object, required)*  
  - `LawfulBases`: Bases for lawful processing.  
  - `ConditionsForConsent`: Consent conditions.  
  - Additional bases (public interest, contractual necessity, etc.).

- **DataSubjectRights** *(array, required)*  
  - Rights afforded to data subjects, mapped to relevant articles.

- **SpecialDataCategories** *(object, optional)*  
  - Definition and processing conditions for sensitive data.

- **ObligationsOfControllersAndProcessors** *(object, required)*  
  - `GeneralDuties`: Overarching duties.  
  - `DataProtectionOfficer`: Requirements for appointing a DPO.  
  - `RecordKeeping`: Documentation obligations.  
  - `DataProtectionImpactAssessments`: DPIA requirements.  
  - `SecurityRequirements`: Security obligations.  
  - `BreachNotifications`: Breach reporting rules.  
  - `ThirdPartyOversight`: Processor contract obligations.

- **CrossBorderTransfers** *(object, optional)*  
  - `AdequacyFramework`: Adequacy decisions.  
  - `StandardContractualClauses`: SCC usage.  
  - `BindingCorporateRules`: BCR provisions.  
  - `DerogationsForSpecificSituations`: Exceptions.

- **SupervisoryAuthority** *(object, optional)*  
  - `Establishment`: Supervisory authority details.  
  - `FunctionsAndPowers`: Key powers and functions.  
  - `AdministrativeSanctions`: Penalty framework.

- **RemediesAndEnforcement** *(object, optional)*  
  - `JudicialRemedies`: Rights of appeal.  
  - `RightToCompensation`: Data subject remedies.  
  - `Penalties`: Administrative and criminal sanctions.

- **FinalProvisions** *(object, optional)*  
  - `CommencementDate`: Effective date.  
  - `ReviewAndAmendment`: Future amendment process.  
  - `ShortTitle`: Official short title.

## How to Use This Documentation
- **Developers**: Use this as a field-by-field reference for building or validating JSON/YAML instances.  
- **Policy Teams**: Ensure all required sections are populated for drafting new governance documents.  
- **Contributors**: Reference this when proposing schema updates or extensions.

