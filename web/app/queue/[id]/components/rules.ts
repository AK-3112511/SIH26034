/**
 * Statute text for each rule the engine evaluates.
 *
 * Keys are the rule ids emitted by `backend/app/services/rules/evaluators.py`.
 * A reviewer signing a verdict should be reading the rule, not its identifier.
 */
export interface RuleMeta {
  label: string;
  section: string;
  desc: string;
}

export const RULE_METADATA: Record<string, RuleMeta> = {
  "6.1.a": {
    label: "Manufacturer / packer details",
    section: "Rule 6(1)(a)",
    desc: "Complete name and postal address of the manufacturer, packer or importer, including PIN code.",
  },
  "6.1.c": {
    label: "Net quantity in metric units",
    section: "Rule 6(1)(c)",
    desc: "Net quantity declared in approved SI metric units (g, kg, ml, l).",
  },
  "6.1.e": {
    label: "Retail sale price",
    section: "Rule 6(1)(e)",
    desc: "Maximum retail price carrying the words 'inclusive of all taxes'.",
  },
  "6.1.g": {
    label: "Consumer care details",
    section: "Rule 6(1)(g)",
    desc: "Name, address, telephone number and email of the consumer care officer.",
  },
  schedule_ii: {
    label: "Minimum declaration height",
    section: "Rule 7(3) / Schedule II",
    desc: "Minimum height of the declaration, set by the area of the principal display panel.",
  },
};

export function ruleMeta(ruleId: string): RuleMeta {
  return (
    RULE_METADATA[ruleId] ?? {
      label: ruleId,
      section: ruleId,
      desc: "Packaged Commodities Rules, 2011.",
    }
  );
}

/** Field names in the order they appear on a package declaration. */
export function humaniseFieldName(fieldName: string): string {
  return fieldName.replace(/_/g, " ");
}
