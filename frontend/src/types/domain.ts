/**
 * Hand-maintained API contract used by screens. Mirrors the Django serializers; the generated
 * `api.d.ts` (npm run gen:api) is the reference when they drift.
 *
 * Money fields are decimal strings ("48500.00"), dates are IST business dates ("2026-10-17")
 * and timestamps are ISO-8601 strings with an offset.
 */

import type { MoneyString } from "@/lib/money";

export type Money = MoneyString;
export type ISODate = string;
export type ISODateTime = string;
export type ID = number;

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

/* ----------------------------------------------------------------- Accounts */

export const ROLES = ["AGENT", "BRANCH_MANAGER", "FINANCE", "ADMIN"] as const;
export type Role = (typeof ROLES)[number];

export interface User {
  id: ID;
  username: string;
  first_name: string;
  last_name: string;
  full_name: string;
  email: string;
  role: Role;
  phone: string;
  branch: ID | null;
  branch_code: string | null;
  branch_name: string | null;
}

export interface UserDetail extends User {
  is_active: boolean;
  last_login: ISODateTime | null;
  date_joined: ISODateTime;
}

export interface UserCreateInput {
  username: string;
  password: string;
  first_name: string;
  last_name?: string;
  email?: string;
  phone?: string;
  role: Role;
  branch?: ID | null;
}

export type UserUpdateInput = Partial<
  Pick<UserCreateInput, "first_name" | "last_name" | "email" | "phone" | "role" | "branch">
>;

export interface UserFilters {
  role?: Role;
  branch?: ID;
  is_active?: boolean;
}

/* ----------------------------------------------------------------- Branches */

export interface Branch {
  id: ID;
  code: string;
  name: string;
  city: string;
  address: string;
  is_active: boolean;
  agent_count: number;
  customer_count: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface BranchCreateInput {
  code: string;
  name: string;
  city: string;
  address?: string;
}

export type BranchUpdateInput = Partial<Pick<Branch, "name" | "city" | "address" | "is_active">>;

/* ---------------------------------------------------------------- Customers */

export interface LoanSummary {
  id: ID;
  loan_number: string;
  status: LoanStatus;
  principal: Money;
  annual_interest_rate: string;
  tenure_months: number;
  emi_amount: Money;
  total_payable: Money;
  amount_paid: Money;
  outstanding: Money;
  overdue_amount: Money;
  next_due_date: ISODate | null;
  disbursed_on: ISODate;
}

export interface Customer {
  id: ID;
  customer_code: string;
  full_name: string;
  /** Masked ("******3210") for finance users. */
  phone: string;
  email: string;
  address: string;
  branch: ID;
  branch_code: string;
  branch_name: string;
  assigned_agent: ID | null;
  assigned_agent_name: string | null;
  is_active: boolean;
  outstanding: Money;
  overdue_amount: Money;
  due_today: Money;
  next_due_date: ISODate | null;
  active_loans: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface CustomerDetail extends Customer {
  loans: LoanSummary[];
}

export interface CustomerCreateInput {
  full_name: string;
  phone: string;
  email?: string;
  address?: string;
  /** Required for admins; managers always create in their own branch. */
  branch?: ID | null;
  assigned_agent?: ID | null;
}

export type CustomerUpdateInput = Partial<
  Pick<Customer, "full_name" | "phone" | "email" | "address" | "is_active">
>;

export interface CustomerFilters {
  branch?: ID;
  agent?: ID;
  unassigned?: boolean;
  is_active?: boolean;
}

export type AgentRouteDue = "overdue" | "today";

/* -------------------------------------------------------------------- Loans */

export type LoanStatus = "ACTIVE" | "CLOSED";
export type InstallmentStatus = "PENDING" | "PARTIALLY_PAID" | "PAID";

export interface NextDue {
  installment_no: number;
  due_date: ISODate;
  amount: Money;
}

export interface Loan {
  id: ID;
  loan_number: string;
  customer: ID;
  customer_code: string;
  customer_name: string;
  customer_phone: string;
  branch: ID;
  branch_code: string;
  branch_name: string;
  agent: ID | null;
  agent_name: string | null;
  principal: Money;
  annual_interest_rate: string;
  tenure_months: number;
  emi_amount: Money;
  total_payable: Money;
  amount_paid: Money;
  outstanding: Money;
  overdue_amount: Money;
  paid_installments: number;
  next_due: NextDue | null;
  disbursed_on: ISODate;
  first_due_date: ISODate;
  status: LoanStatus;
  closed_at: ISODateTime | null;
  /** True once any repayment exists; terms can no longer be edited. */
  terms_locked: boolean;
  created_by: ID;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface LoanTermsInput {
  principal: Money;
  /** Annual percentage as a string, e.g. "12.50". */
  annual_interest_rate: string;
  tenure_months: number;
  disbursed_on?: ISODate;
  first_due_date?: ISODate;
}

export interface LoanCreateInput extends LoanTermsInput {
  customer_id: ID;
}

export interface LoanFilters {
  branch?: ID;
  customer?: ID;
  agent?: ID;
  status?: LoanStatus;
  disbursed_from?: ISODate;
  disbursed_to?: ISODate;
  overdue?: boolean;
}

export interface Installment {
  id: ID;
  installment_no: number;
  due_date: ISODate;
  principal_component: Money;
  interest_component: Money;
  amount_due: Money;
  amount_paid: Money;
  outstanding: Money;
  status: InstallmentStatus;
  is_overdue: boolean;
  paid_at: ISODateTime | null;
}

export interface ScheduleRow {
  installment_no: number;
  due_date: ISODate;
  opening_balance: Money;
  principal_component: Money;
  interest_component: Money;
  amount_due: Money;
  closing_balance: Money;
}

export interface SchedulePreview {
  principal: Money;
  annual_interest_rate: string;
  tenure_months: number;
  disbursed_on: ISODate;
  first_due_date: ISODate;
  emi_amount: Money;
  total_payable: Money;
  total_interest: Money;
  installments: ScheduleRow[];
}

export interface RepaymentAllocation {
  installment: ID;
  installment_no: number;
  due_date: ISODate;
  amount: Money;
  reversed_at: ISODateTime | null;
}

export interface Repayment {
  id: ID;
  receipt_number: string;
  amount: Money;
  mode: PaymentMode;
  status: CollectionStatus;
  agent: ID | null;
  agent_name: string | null;
  gateway_payment_id: string | null;
  remarks: string;
  collected_at: ISODateTime;
  submitted_at: ISODateTime | null;
  branch_received_at: ISODateTime | null;
  deposited_at: ISODateTime | null;
  settled_at: ISODateTime | null;
  voided_at: ISODateTime | null;
  void_reason: string;
  submission_number: string | null;
  deposit_number: string | null;
  allocations: RepaymentAllocation[];
}

/* -------------------------------------------------------------- Collections */

export type PaymentMode = "CASH" | "UPI";
export const COLLECTION_STATUSES = [
  "COLLECTED",
  "SUBMITTED",
  "BRANCH_RECEIVED",
  "DEPOSITED",
  "SETTLED",
  "VOIDED",
] as const;
export type CollectionStatus = (typeof COLLECTION_STATUSES)[number];

export interface Collection {
  id: ID;
  receipt_number: string;
  loan: ID;
  loan_number: string;
  customer: ID;
  customer_code: string;
  customer_name: string;
  branch: ID;
  branch_code: string;
  agent: ID | null;
  agent_name: string | null;
  amount: Money;
  mode: PaymentMode;
  status: CollectionStatus;
  collected_at: ISODateTime;
  submitted_at: ISODateTime | null;
  branch_received_at: ISODateTime | null;
  deposited_at: ISODateTime | null;
  settled_at: ISODateTime | null;
  voided_at: ISODateTime | null;
  gateway_payment_id: string | null;
  remarks: string;
  /** Loan balance right after this receipt was applied, as recorded; never updated later. */
  balance_after: Money | null;
}

export interface Allocation {
  id: ID;
  installment: ID;
  installment_no: number;
  due_date: ISODate;
  amount: Money;
  reversed_at: ISODateTime | null;
}

export interface TimelineStep {
  status: CollectionStatus;
  label: string;
  reached: boolean;
  at: ISODateTime | null;
  /** Receipt, submission or deposit number for the step. */
  reference: string | null;
}

/** The receipt. */
export interface CollectionDetail extends Collection {
  /** The loan's balance today; receipts show `balance_after` instead. */
  loan_outstanding: Money;
  submission: ID | null;
  submission_number: string | null;
  deposit: ID | null;
  deposit_number: string | null;
  void_reason: string;
  voided_by: ID | null;
  voided_by_name: string | null;
  allocations: Allocation[];
  timeline: TimelineStep[];
}

export interface CollectionCreateInput {
  loan_id: ID;
  amount: Money;
  /** Only CASH; UPI goes through the payment gateway. */
  mode?: "CASH";
  remarks?: string;
  /** Record despite a matching receipt moments ago (after POSSIBLE_DUPLICATE). */
  confirm_duplicate?: boolean;
}

export interface CollectionFilters {
  date?: ISODate;
  date_from?: ISODate;
  date_to?: ISODate;
  branch?: ID;
  agent?: ID;
  loan?: ID;
  customer?: ID;
  status?: CollectionStatus[];
  mode?: PaymentMode;
}

export interface DailySummary {
  date: ISODate;
  count: number;
  total_amount: Money;
  cash_count: number;
  cash_amount: Money;
  upi_count: number;
  upi_amount: Money;
  voided_count: number;
  /** Cash receipts not yet handed over (any day). */
  unsubmitted_count: number;
  unsubmitted_cash: Money;
}

/* ----------------------------------------------------------- Reconciliation */

export type SubmissionStatus = "SUBMITTED" | "APPROVED" | "APPROVED_WITH_DISCREPANCY" | "REJECTED";

/** Rupee denomination ("500") -> count of notes or coins. */
export type Denominations = Partial<Record<DenominationKey, number>>;
export const DENOMINATION_VALUES = [2000, 500, 200, 100, 50, 20, 10, 5, 2, 1] as const;
export type DenominationKey = `${(typeof DENOMINATION_VALUES)[number]}`;

export interface CashSubmission {
  id: ID;
  submission_number: string;
  agent: ID;
  agent_name: string;
  agent_username: string;
  branch: ID;
  branch_code: string;
  expected_amount: Money;
  declared_amount: Money;
  received_amount: Money | null;
  /** Expected minus received: positive is a shortage, negative an excess. */
  difference: Money | null;
  status: SubmissionStatus;
  collection_count: number;
  submitted_at: ISODateTime;
  reviewed_at: ISODateTime | null;
  reviewed_by: ID | null;
  reviewed_by_name: string | null;
  review_remarks: string;
  rejection_reason: string;
  deposit: ID | null;
  deposit_number: string | null;
}

export interface SubmissionCollection {
  id: ID;
  receipt_number: string;
  loan: ID;
  loan_number: string;
  customer: ID;
  customer_name: string;
  amount: Money;
  status: CollectionStatus;
  collected_at: ISODateTime;
}

export interface SubmissionDiscrepancy {
  id: ID;
  kind: DiscrepancyKind;
  direction: DiscrepancyDirection;
  amount: Money;
  status: DiscrepancyStatus;
  reason_code: DiscrepancyReasonCode;
  notes: string;
  resolution_notes: string;
  resolved_at: ISODateTime | null;
  created_at: ISODateTime;
}

export interface CashSubmissionDetail extends CashSubmission {
  /** The agent's own count; null when handed over as receipted. */
  denominations: Denominations | null;
  /** The branch manager's count, when itemised. */
  received_denominations: Denominations | null;
  collections: SubmissionCollection[];
  discrepancies: SubmissionDiscrepancy[];
}

export interface SubmissionCreateInput {
  collection_ids: ID[];
  declared_amount: Money;
  denominations?: Denominations | null;
}

export interface SubmissionApproveInput {
  received_amount: Money;
  denominations?: Denominations | null;
  /** Required when received differs from expected. */
  reason_code?: DiscrepancyReasonCode;
  remarks?: string;
}

export interface SubmissionRejectInput {
  reason: string;
}

export interface SubmissionFilters {
  status?: SubmissionStatus[];
  agent?: ID;
  branch?: ID;
  date_from?: ISODate;
  date_to?: ISODate;
  awaiting_deposit?: boolean;
}

export type DiscrepancyKind =
  | "CASH_SHORTAGE"
  | "CASH_EXCESS"
  | "DEPOSIT_MISMATCH"
  | "SETTLEMENT_MISMATCH"
  | "GATEWAY_MISMATCH";
export type DiscrepancyDirection = "SHORT" | "EXCESS";
export type DiscrepancyStatus = "OPEN" | "RESOLVED" | "WRITTEN_OFF";
export type DiscrepancyReasonCode =
  | "COUNTING_ERROR"
  | "AGENT_SHORTAGE"
  | "BANK_CHARGES"
  | "BANK_ERROR"
  | "OTHER";

export const DISCREPANCY_KIND_LABEL: Record<DiscrepancyKind, string> = {
  CASH_SHORTAGE: "Cash shortage",
  CASH_EXCESS: "Cash excess",
  DEPOSIT_MISMATCH: "Deposit mismatch",
  SETTLEMENT_MISMATCH: "Settlement mismatch",
  GATEWAY_MISMATCH: "Gateway mismatch",
};

export const DISCREPANCY_REASON_LABEL: Record<DiscrepancyReasonCode, string> = {
  COUNTING_ERROR: "Counting error",
  AGENT_SHORTAGE: "Agent shortage",
  BANK_CHARGES: "Bank charges",
  BANK_ERROR: "Bank error",
  OTHER: "Other",
};

export interface Discrepancy {
  id: ID;
  kind: DiscrepancyKind;
  direction: DiscrepancyDirection;
  amount: Money;
  status: DiscrepancyStatus;
  reason_code: DiscrepancyReasonCode;
  notes: string;
  submission: ID | null;
  submission_number: string | null;
  deposit: ID | null;
  deposit_number: string | null;
  branch: ID | null;
  branch_code: string | null;
  agent: ID | null;
  agent_name: string | null;
  raised_by: ID | null;
  raised_by_name: string | null;
  resolution_notes: string;
  resolved_by: ID | null;
  resolved_by_name: string | null;
  resolved_at: ISODateTime | null;
  created_at: ISODateTime;
}

export interface DiscrepancyCreateInput {
  kind: DiscrepancyKind;
  direction?: DiscrepancyDirection;
  amount: Money;
  reason_code: DiscrepancyReasonCode;
  notes: string;
  submission_id?: ID;
  deposit_id?: ID;
}

export interface DiscrepancyResolveInput {
  outcome: "RESOLVED" | "WRITTEN_OFF";
  resolution_notes: string;
}

export interface DiscrepancyFilters {
  kind?: DiscrepancyKind[];
  status?: DiscrepancyStatus[];
  direction?: DiscrepancyDirection;
  reason_code?: DiscrepancyReasonCode;
  branch?: ID;
  agent?: ID;
  submission?: ID;
  deposit?: ID;
  date_from?: ISODate;
  date_to?: ISODate;
}

export interface SummaryParams {
  date_from?: ISODate;
  date_to?: ISODate;
  branch?: ID;
}

export interface BranchSummaryMetrics {
  expected_due: Money;
  collected_cash: Money;
  collected_upi: Money;
  collected_total: Money;
  held_by_agents: Money;
  pending_verification: Money;
  pending_submissions: number;
  received_at_branch: Money;
  at_branch_not_deposited: Money;
  deposited: Money;
  pending_settlement: Money;
  delayed_deposits: number;
  settled_cash: Money;
  settled_upi: Money;
  settled_total: Money;
  open_discrepancies: number;
  open_shortage: Money;
  open_excess: Money;
}

export interface BranchSummaryRow extends BranchSummaryMetrics {
  branch_id: ID;
  branch_code: string;
  branch_name: string;
}

export interface BranchSummary {
  date_from: ISODate;
  date_to: ISODate;
  totals: BranchSummaryMetrics;
  branches: BranchSummaryRow[];
}

export interface AgentSummaryMetrics {
  collected_cash: Money;
  collected_upi: Money;
  collection_count: number;
  submitted: Money;
  received: Money;
  cash_in_hand: Money;
  receipts_in_hand: number;
  pending_verification: Money;
  held_under_1d: Money;
  held_1_to_2d: Money;
  held_over_2d: Money;
  open_shortage: Money;
}

export interface AgentSummaryRow extends AgentSummaryMetrics {
  agent_id: ID;
  username: string;
  full_name: string;
  branch_id: ID | null;
  branch_code: string | null;
  oldest_held_at: ISODateTime | null;
  oldest_held_hours: number | null;
}

export interface AgentsSummary {
  date_from: ISODate;
  date_to: ISODate;
  as_of: ISODateTime;
  totals: AgentSummaryMetrics;
  agents: AgentSummaryRow[];
}

/* ----------------------------------------------------------------- Deposits */

export type DepositSource = "CASH" | "GATEWAY";
export type DepositStatus = "PENDING" | "SETTLED" | "SETTLED_WITH_MISMATCH" | "FAILED";

export interface BankAccount {
  id: ID;
  bank_name: string;
  account_name: string;
  masked_account_number: string;
  ifsc: string;
  is_gateway: boolean;
  is_active: boolean;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export type BankAccountBrief = Pick<
  BankAccount,
  "id" | "bank_name" | "account_name" | "masked_account_number" | "is_gateway"
>;

export interface BankAccountWriteInput {
  bank_name: string;
  account_name: string;
  /** Full number (6-18 digits); only the last four are stored. */
  account_number: string;
  ifsc?: string;
  is_gateway?: boolean;
  is_active?: boolean;
}

export interface Deposit {
  id: ID;
  deposit_number: string;
  source: DepositSource;
  status: DepositStatus;
  branch: ID | null;
  branch_code: string | null;
  bank_account: BankAccountBrief;
  reference_number: string;
  deposit_date: ISODate;
  expected_amount: Money;
  deposited_amount: Money;
  fee_amount: Money;
  tax_amount: Money;
  settled_amount: Money | null;
  settled_on: ISODate | null;
  is_delayed: boolean;
  days_pending: number | null;
  created_by: ID;
  created_by_name: string;
  created_at: ISODateTime;
}

export interface DepositSubmission {
  id: ID;
  submission_number: string;
  status: SubmissionStatus;
  agent: ID;
  agent_name: string;
  expected_amount: Money;
  received_amount: Money | null;
  difference: Money | null;
  submitted_at: ISODateTime;
  reviewed_at: ISODateTime | null;
  reviewed_by_name: string | null;
}

export interface ReconciliationChain {
  reconciled_amount: Money;
  deposited_amount: Money;
  fee_amount: Money;
  tax_amount: Money;
  expected_settlement_amount: Money;
  settled_amount: Money | null;
  /** Positive when money is short. */
  deposit_difference: Money;
  settlement_difference: Money | null;
  total_difference: Money | null;
}

export interface DepositDetail extends Deposit {
  settlement_reference: string;
  remarks: string;
  failure_reason: string;
  settled_at: ISODateTime | null;
  settled_by: ID | null;
  settled_by_name: string | null;
  failed_at: ISODateTime | null;
  failed_by: ID | null;
  failed_by_name: string | null;
  collections_count: number;
  submissions: DepositSubmission[];
  discrepancies: Pick<
    Discrepancy,
    "id" | "kind" | "direction" | "amount" | "status" | "reason_code" | "created_at"
  >[];
  reconciliation: ReconciliationChain;
}

export interface DepositCreateInput {
  submission_ids: ID[];
  bank_account_id: ID;
  deposited_amount: Money;
  deposit_date: ISODate;
  reference_number: string;
  remarks?: string;
}

export interface DepositSettleInput {
  settled_amount: Money;
  settled_on: ISODate;
  settlement_reference: string;
  remarks?: string;
  /** Classifies the settlement mismatch when the credit differs; the server defaults to BANK_ERROR. */
  reason_code?: DiscrepancyReasonCode;
}

export interface DepositFailInput {
  reason: string;
}

export interface DepositFilters {
  status?: DepositStatus[];
  source?: DepositSource;
  branch?: ID;
  bank_account?: ID;
  date_from?: ISODate;
  date_to?: ISODate;
  delayed?: boolean;
}

export interface PendingCashSubmission extends DepositSubmission {
  branch: ID;
  branch_code: string;
}

export interface PendingCash {
  count: number;
  total_amount: Money;
  submissions: PendingCashSubmission[];
}

export interface UnsettledUpiCollection {
  id: ID;
  receipt_number: string;
  amount: Money;
  collected_at: ISODateTime;
  gateway_payment_id: string | null;
  branch: ID;
  branch_code: string;
  loan_number: string;
  customer_name: string;
}

export interface UnsettledUpi {
  count: number;
  total_amount: Money;
  collections: UnsettledUpiCollection[];
}

export interface GatewaySettlementInput {
  /** Either collection_ids or up_to_date. */
  collection_ids?: ID[];
  up_to_date?: ISODate;
  gross_amount: Money;
  fee_amount?: Money;
  tax_amount?: Money;
  net_amount: Money;
  utr: string;
  settled_on: ISODate;
  remarks?: string;
}

export interface GatewaySettlementFilters {
  status?: DepositStatus[];
  date_from?: ISODate;
  date_to?: ISODate;
}

/* ----------------------------------------------------------------- Payments */

export type GatewayProvider = "RAZORPAY" | "CASHFREE" | "MOCK";
/** REFUND_DUE: captured after the loan was paid off by other means; owed back to the customer. */
export type GatewayOrderStatus = "CREATED" | "PAID" | "FAILED" | "EXPIRED" | "REFUND_DUE";

export interface GatewayOrder {
  id: ID;
  provider: GatewayProvider;
  provider_order_id: string;
  receipt: string;
  loan: ID;
  loan_number: string;
  customer: ID;
  customer_name: string;
  branch: ID;
  branch_code: string;
  agent: ID;
  agent_name: string;
  amount: Money;
  amount_paise: number;
  status: GatewayOrderStatus;
  provider_payment_id: string | null;
  collection: ID | null;
  receipt_number: string | null;
  paid_at: ISODateTime | null;
  failed_at: ISODateTime | null;
  failure_reason: string;
  created_at: ISODateTime;
  expires_at: ISODateTime;
}

export interface GatewayConfig {
  provider: GatewayProvider;
  /** Public checkout key (Razorpay); empty for Cashfree and the mock gateway. */
  key_id: string;
  /** `test`/`live` (Razorpay, mock) or `sandbox`/`production` (Cashfree). */
  environment: string;
  currency: string;
  /** Empty for the mock gateway. */
  checkout_script: string;
  checkout_timeout_seconds: number;
}

export interface CheckoutOptions extends GatewayConfig {
  order_id: string;
  /** Payment session the Cashfree checkout opens with; empty for other gateways. */
  session_id: string;
  amount: Money;
  amount_paise: number;
  description: string;
  expires_at: ISODateTime;
  prefill: { name: string; contact: string; email: string };
  notes: Record<string, string>;
}

export interface OrderCreated {
  order: GatewayOrder;
  checkout: CheckoutOptions;
}

export interface OrderCreateInput {
  loan_id: ID;
  amount: Money;
}

export interface VerifyPaymentInput {
  order_id: string;
  payment_id: string;
  signature: string;
}

export interface PaymentResult {
  order: GatewayOrder;
  receipt: CollectionDetail | null;
  /** A gateway attempt is still undecided (status checks only), even if an earlier one failed. */
  payment_in_progress: boolean;
}

export type MockPayOutcome = "success" | "failure";

export interface GatewayOrderFilters {
  status?: GatewayOrderStatus[];
  provider?: GatewayProvider;
  loan?: ID;
  agent?: ID;
  branch?: ID;
  date_from?: ISODate;
  date_to?: ISODate;
}

/* ---------------------------------------------------------------- Dashboard */

export interface DashboardParams {
  /** Defaults to the first day of date_to's month. */
  date_from?: ISODate;
  /** Defaults to today (IST). */
  date_to?: ISODate;
  branch?: ID;
  agent?: ID;
  /** Receipt status; narrows every receipt figure. Voided is not accepted. */
  status?: Exclude<CollectionStatus, "VOIDED">;
}

export interface Tally {
  amount: Money;
  count: number;
}

export type CashAgeingBucket = "under_1_day" | "1_to_2_days" | "over_2_days";

export interface DashboardSummary {
  date_from: ISODate;
  date_to: ISODate;
  expected: Tally;
  collected: Tally & { cash: Tally; upi: Tally };
  voided: Tally;
  cash_with_agents: Tally;
  pending_verification: Tally;
  cash_ageing: (Tally & { bucket: CashAgeingBucket; label: string })[];
  branch_received: Tally;
  at_branch: Tally;
  /** Branch cash deposits awaiting bank confirmation, whenever deposited (now). */
  pending_deposits: Tally;
  deposits: Tally & { by_status: (Tally & { status: DepositStatus })[] };
  settled: Tally;
  delayed_settlements: Tally;
  outstanding: Tally;
  overdue: Tally;
  discrepancies: {
    open: Tally;
    open_by_kind: (Tally & { kind: DiscrepancyKind })[];
    raised: Tally;
    resolved: Tally;
  };
  /** Percentage string, e.g. "93.50". */
  collection_efficiency: string | null;
  deposit_accuracy: string | null;
  avg_settlement_lag_days: string | null;
}

export interface TrendPoint {
  date: ISODate;
  expected: Money;
  collected: Money;
  settled: Money;
}

export type LifecycleStage = "COLLECTED" | "BRANCH_RECEIVED" | "DEPOSITED" | "SETTLED";

export interface Lifecycle {
  date_from: ISODate;
  date_to: ISODate;
  expected: Tally;
  stages: (Tally & { stage: LifecycleStage | string; label: string })[];
  by_status: (Tally & { status: CollectionStatus; label: string })[];
}

interface TeamRow {
  expected: Tally;
  collected: Tally;
  cash_with_agents: Tally;
  pending_verification: Tally;
  branch_received: Tally;
  outstanding: Tally;
  overdue: Tally;
  open_discrepancies: Tally;
  collection_efficiency: string | null;
}

export interface BranchRow extends TeamRow {
  branch: Pick<Branch, "id" | "code" | "name">;
  at_branch: Tally;
  deposited: Tally;
  settled: Tally;
  delayed_settlements: Tally;
}

export interface AgentRow extends TeamRow {
  agent: {
    id: ID;
    username: string;
    full_name: string;
    branch: ID | null;
    branch_code: string | null;
    is_active: boolean;
  };
  oldest_cash_held_at: ISODateTime | null;
  rejected_submissions: Tally;
}

export type ReportName = "collections" | "submissions" | "deposits" | "discrepancies";

export interface ReportParams extends Omit<DashboardParams, "status"> {
  status?: string;
}

/* -------------------------------------------------------------------- Audit */

export interface AuditLog {
  id: ID;
  created_at: ISODateTime;
  action: string;
  action_label: string;
  entity_type: string;
  entity_id: string;
  /** What the record is called on screen: "Receipt", "Hand-over", "Deposit"… */
  entity_label: string;
  /** Its document number (receipt, hand-over, deposit, loan…), when it has one. */
  entity_reference: string | null;
  actor: ID | null;
  actor_username: string | null;
  actor_name: string | null;
  branch: ID | null;
  branch_code: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string;
  /** Empty for entries written outside a request, such as seeds and scheduled jobs. */
  request_id: string | null;
}

export interface AuditLogFilters {
  entity_type?: string;
  entity_id?: string;
  actor?: ID;
  branch?: ID;
  action?: string;
  date_from?: ISODate;
  date_to?: ISODate;
}

/* ------------------------------------------------------------- List params */

/** Common list query params understood by every paginated endpoint. */
export interface ListParams {
  page?: number;
  page_size?: number;
  /** Field name, prefix "-" for descending, e.g. "-collected_at". */
  ordering?: string;
  search?: string;
}
