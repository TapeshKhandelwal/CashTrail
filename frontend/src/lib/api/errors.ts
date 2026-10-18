import type { ApiErrorBody } from "@/types/domain";

/** Error codes the backend raises (plus BFF/network ones), for exhaustive handling in screens. */
export type ApiErrorCode =
  | "VALIDATION_ERROR"
  | "VALIDATION_FAILED"
  | "NOT_FOUND"
  | "NOT_AUTHENTICATED"
  | "AUTHENTICATION_FAILED"
  | "NO_ACTIVE_ACCOUNT"
  | "TOKEN_NOT_VALID"
  | "PERMISSION_DENIED"
  | "SCOPE_VIOLATION"
  | "THROTTLED"
  | "INVALID_STATE_TRANSITION"
  | "RECORD_LOCKED"
  | "OVER_COLLECTION"
  | "POSSIBLE_DUPLICATE"
  | "DUPLICATE_BANK_REFERENCE"
  | "DUPLICATE_RECORD"
  | "DUPLICATE_REQUEST"
  | "DUPLICATE_PAYMENT"
  | "IDEMPOTENCY_CONFLICT"
  | "IDEMPOTENCY_KEY_REQUIRED"
  | "PENDING_SUBMISSION_EXISTS"
  | "SUBMISSION_ALREADY_DEPOSITED"
  | "SEGREGATION_OF_DUTIES"
  | "DENOMINATION_MISMATCH"
  | "CUSTOMER_INACTIVE"
  | "LOAN_NOT_ACTIVE"
  | "GATEWAY_ERROR"
  | "GATEWAY_MISMATCH"
  | "GATEWAY_ACCOUNT_EXISTS"
  | "INVALID_SIGNATURE"
  | "ORDER_ALREADY_PAID"
  | "PAYMENT_AMOUNT_MISMATCH"
  | "PROTECTED_RECORD"
  | "INVALID_REFERENCE"
  | "INTEGRITY_ERROR"
  | "INTERNAL_ERROR"
  | "SESSION_EXPIRED"
  | "NETWORK_ERROR"
  | "UPSTREAM_UNAVAILABLE";

/** Plain-English copy for each code. Screens may override with context-specific wording. */
export const FRIENDLY_MESSAGES: Partial<Record<ApiErrorCode, string>> = {
  VALIDATION_ERROR: "Some details need fixing. Check the highlighted fields.",
  NOT_FOUND: "We couldn't find that record. It may have been removed or is outside your access.",
  NOT_AUTHENTICATED: "Your session has ended. Sign in again to continue.",
  SESSION_EXPIRED: "Your session has ended. Sign in again to continue.",
  TOKEN_NOT_VALID: "Your session has ended. Sign in again to continue.",
  NO_ACTIVE_ACCOUNT: "That username and password don't match.",
  AUTHENTICATION_FAILED: "That username and password don't match.",
  PERMISSION_DENIED: "You don't have permission to do that.",
  SCOPE_VIOLATION: "That record belongs to another branch or agent.",
  THROTTLED: "Too many attempts. Try again in a minute.",
  INVALID_STATE_TRANSITION: "This was already updated by someone else. Refresh to see the latest.",
  RECORD_LOCKED: "This record is reconciled and locked. Corrections need a new entry.",
  OVER_COLLECTION: "That's more than the outstanding balance on this loan.",
  POSSIBLE_DUPLICATE: "A matching receipt was recorded moments ago.",
  DUPLICATE_BANK_REFERENCE: "This slip or reference number has already been used for this account.",
  DUPLICATE_RECORD: "A record with these details already exists.",
  DUPLICATE_REQUEST: "This request is already being processed. Wait a moment and try again.",
  DUPLICATE_PAYMENT: "This payment has already been recorded.",
  IDEMPOTENCY_CONFLICT: "This form was already submitted with different values. Reload and try again.",
  PENDING_SUBMISSION_EXISTS: "You already have a hand-over waiting to be counted.",
  SUBMISSION_ALREADY_DEPOSITED: "One of these hand-overs has already been deposited.",
  SEGREGATION_OF_DUTIES: "You can't review cash you collected yourself.",
  DENOMINATION_MISMATCH: "The note count doesn't add up to the amount entered.",
  CUSTOMER_INACTIVE: "This customer is inactive.",
  LOAN_NOT_ACTIVE: "This loan is closed.",
  GATEWAY_ERROR: "The payment gateway didn't respond. Try again in a moment.",
  GATEWAY_MISMATCH: "The settlement doesn't match the captured UPI payments.",
  GATEWAY_ACCOUNT_EXISTS: "Only one active gateway settlement account is allowed.",
  INVALID_SIGNATURE: "We couldn't verify this payment. Check its status before retrying.",
  ORDER_ALREADY_PAID: "This UPI order has already been paid.",
  PAYMENT_AMOUNT_MISMATCH: "The amount paid doesn't match the order.",
  PROTECTED_RECORD: "This record is in use and can't be removed.",
  INTERNAL_ERROR: "Something went wrong on our side. Try again.",
  NETWORK_ERROR: "You appear to be offline. Check your connection and try again.",
  UPSTREAM_UNAVAILABLE: "CashTrail's server isn't responding. Try again shortly.",
};

const GENERIC = "Something went wrong. Try again.";

/** Codes whose server message names the exact clash ("This username is already taken."). */
const SERVER_WORDED: readonly string[] = ["DUPLICATE_RECORD"];

export type FieldErrors = Record<string, string[]>;

export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode | (string & {});
  readonly details: Record<string, unknown>;
  readonly requestId: string | null;

  constructor(
    status: number,
    body: ApiErrorBody["error"],
    requestId: string | null = null,
  ) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details ?? {};
    this.requestId = requestId;
  }

  /** Copy suitable for a toast or an error state. */
  get friendlyMessage(): string {
    if (SERVER_WORDED.includes(this.code) && this.message) return this.message;
    return FRIENDLY_MESSAGES[this.code as ApiErrorCode] ?? this.message ?? GENERIC;
  }

  /**
   * Messages per field. VALIDATION_ERROR details are DRF's own messages, e.g. `{ amount: ["..."] }`;
   * other codes name the field with the value that broke the rule, so it gets the server's message.
   */
  get fieldErrors(): FieldErrors {
    const errors: FieldErrors = {};
    for (const [field, value] of Object.entries(this.details)) {
      if (this.code !== "VALIDATION_ERROR") errors[field] = [this.message || GENERIC];
      else if (Array.isArray(value)) errors[field] = value.map(String);
      else if (typeof value === "string") errors[field] = [value];
    }
    return errors;
  }

  is(...codes: ApiErrorCode[]): boolean {
    return codes.includes(this.code as ApiErrorCode);
  }

  get isAuthError(): boolean {
    return this.status === 401;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as ApiErrorBody).error?.code === "string"
  );
}

/** Builds an ApiError from any failed Response, tolerating non-envelope bodies. */
export async function toApiError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("x-request-id");
  const body: unknown = await response.json().catch(() => null);
  if (isErrorBody(body)) return new ApiError(response.status, body.error, requestId);
  const code = response.status >= 500 ? "UPSTREAM_UNAVAILABLE" : `HTTP_${response.status}`;
  return new ApiError(response.status, { code, message: GENERIC, details: {} }, requestId);
}

export function networkError(): ApiError {
  return new ApiError(0, {
    code: "NETWORK_ERROR",
    message: FRIENDLY_MESSAGES.NETWORK_ERROR ?? GENERIC,
    details: {},
  });
}

/** Message for anything thrown by a query or mutation. */
export function errorMessage(error: unknown): string {
  if (isApiError(error)) return error.friendlyMessage;
  if (error instanceof Error && error.message) return error.message;
  return GENERIC;
}
