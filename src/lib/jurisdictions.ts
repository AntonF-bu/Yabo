/** Supported tax jurisdictions for Trading DNA context input. */

export interface Jurisdiction {
  code: string;
  label: string;
}

export const JURISDICTIONS: Jurisdiction[] = [
  // US States
  { code: "US_CA", label: "California, US" },
  { code: "US_NY", label: "New York, US" },
  { code: "US_NJ", label: "New Jersey, US" },
  { code: "US_IL", label: "Illinois, US" },
  { code: "US_MA", label: "Massachusetts, US" },
  { code: "US_TX", label: "Texas, US" },
  { code: "US_FL", label: "Florida, US" },
  { code: "US_WA", label: "Washington, US" },
  { code: "US_NV", label: "Nevada, US" },
  { code: "US_TN", label: "Tennessee, US" },
  { code: "US_WY", label: "Wyoming, US" },
  { code: "US_CT", label: "Connecticut, US" },
  { code: "US_PA", label: "Pennsylvania, US" },
  { code: "US_OH", label: "Ohio, US" },
  { code: "US_CO", label: "Colorado, US" },
  { code: "US_GA", label: "Georgia, US" },
  { code: "US_NC", label: "North Carolina, US" },
  { code: "US_VA", label: "Virginia, US" },
  { code: "US_AZ", label: "Arizona, US" },
  { code: "US_OR", label: "Oregon, US" },
  { code: "US_SD", label: "South Dakota, US" },
  { code: "US_AK", label: "Alaska, US" },
  { code: "US_NH", label: "New Hampshire, US" },
  // International
  { code: "RO", label: "Romania" },
  { code: "SG", label: "Singapore" },
  { code: "UK", label: "United Kingdom" },
  { code: "DE", label: "Germany" },
  { code: "AU", label: "Australia" },
  { code: "JP", label: "Japan" },
  { code: "CAN", label: "Canada" },
  { code: "CH", label: "Switzerland" },
  { code: "HK", label: "Hong Kong" },
  { code: "AE", label: "United Arab Emirates" },
];
