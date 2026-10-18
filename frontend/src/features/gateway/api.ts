import { keepPreviousData, queryOptions } from "@tanstack/react-query";

import { useApiMutation, type ApiMutationOptions } from "@/hooks/use-api";
import { api } from "@/lib/api/client";
import { MONEY_KEYS, qk } from "@/lib/api/query-keys";
import type {
  Deposit,
  DepositDetail,
  GatewayConfig,
  GatewayOrder,
  GatewayOrderFilters,
  GatewaySettlementFilters,
  GatewaySettlementInput,
  ID,
  ISODate,
  ListParams,
  MockPayOutcome,
  OrderCreated,
  OrderCreateInput,
  Paginated,
  PaymentResult,
  UnsettledUpi,
  VerifyPaymentInput,
} from "@/types/domain";

/* ------------------------------------------------- UPI payments (agent) */

export const paymentQueries = {
  /** Which gateway is active (RAZORPAY | MOCK) and its public checkout key. */
  config: () =>
    queryOptions({
      queryKey: qk.payments.config,
      queryFn: ({ signal }) => api.get<GatewayConfig>("payments/config", undefined, { signal }),
      staleTime: Infinity,
    }),
  orders: (params: GatewayOrderFilters & ListParams = {}) =>
    queryOptions({
      queryKey: qk.payments.list(params),
      queryFn: ({ signal }) => api.get<Paginated<GatewayOrder>>("payments/orders", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  /** Poll while waiting for payment: `refetchInterval: 2000` until status leaves CREATED. */
  order: (id: ID) =>
    queryOptions({
      queryKey: qk.payments.detail(id),
      queryFn: ({ signal }) => api.get<GatewayOrder>(`payments/orders/${id}`, undefined, { signal }),
    }),
  /**
   * Has the gateway confirmed the order's payment? Asks it (POST …/refresh) and records a
   * capture as the receipt. Safe to repeat, so it is polled like a read while the customer pays
   * through a checkout that returns nothing the server could verify (Cashfree).
   */
  confirmation: (id: ID) =>
    queryOptions({
      queryKey: qk.payments.confirmation(id),
      queryFn: ({ signal }) => api.post<PaymentResult>(`payments/orders/${id}/refresh`, undefined, { signal }).then((r) => r.data),
      staleTime: 0,
      gcTime: 0,
      retry: false,
    }),
};

export function useCreateUpiOrder(options?: ApiMutationOptions<OrderCreated, OrderCreateInput>) {
  return useApiMutation(
    (body: OrderCreateInput, { idempotencyKey }) =>
      api.post<OrderCreated>("payments/orders", body, { idempotencyKey }).then((r) => r.data),
    { handledErrors: ["OVER_COLLECTION"], ...options },
  );
}

/** Confirms a Razorpay checkout; the receipt comes back in `receipt`. */
export function useVerifyPayment(options?: ApiMutationOptions<PaymentResult, VerifyPaymentInput>) {
  return useApiMutation(
    (body: VerifyPaymentInput) => api.post<PaymentResult>("payments/verify", body).then((r) => r.data),
    { invalidate: MONEY_KEYS, ...options },
  );
}

/** Mock gateway only (`payments/config` reports MOCK): simulate the customer paying or failing. */
export function useMockPay(options?: ApiMutationOptions<PaymentResult, { orderId: ID; outcome: MockPayOutcome }>) {
  return useApiMutation(
    ({ orderId, outcome }: { orderId: ID; outcome: MockPayOutcome }) =>
      api.post<PaymentResult>(`payments/mock/${orderId}/pay`, { outcome }).then((r) => r.data),
    { invalidate: MONEY_KEYS, ...options },
  );
}

/* --------------------------------------------- Gateway settlements (finance) */

export const gatewaySettlementQueries = {
  list: (params: GatewaySettlementFilters & ListParams = {}) =>
    queryOptions({
      queryKey: qk.gatewaySettlements.list(params),
      queryFn: ({ signal }) => api.get<Paginated<Deposit>>("gateway-settlements", params, { signal }),
      placeholderData: keepPreviousData,
    }),
  /** Captured UPI payments awaiting settlement, optionally captured on or before a date. */
  pending: (params: { up_to_date?: ISODate } = {}) =>
    queryOptions({
      queryKey: qk.gatewaySettlements.pending(params),
      queryFn: ({ signal }) => api.get<UnsettledUpi>("gateway-settlements/pending", params, { signal }),
    }),
};

export function useRecordGatewaySettlement(options?: ApiMutationOptions<DepositDetail, GatewaySettlementInput>) {
  return useApiMutation(
    (body: GatewaySettlementInput, { idempotencyKey }) =>
      api.post<DepositDetail>("gateway-settlements", body, { idempotencyKey }).then((r) => r.data),
    { invalidate: MONEY_KEYS, ...options },
  );
}
