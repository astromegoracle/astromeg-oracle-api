const test = require("node:test");
const assert = require("node:assert/strict");
const pricing = require("../pricing-config.js");

const futureAccessEnd = "2027-01-01T00:00:00.000Z";
const pastAccessEnd = "2025-01-01T00:00:00.000Z";
const evaluationDate = new Date("2026-07-14T00:00:00.000Z");

test("pricing catalog contains only the four approved public plans", () => {
  assert.deepEqual(Object.keys(pricing.plans).sort(), Object.values(pricing.plan_ids).sort());
  assert.equal(pricing.configuration_status, "draft_app_preview_only");
  assert.equal(pricing.deployment_target, "none");
  assert.equal(pricing.checkout_activation_requires_approval, true);
  assert.deepEqual(pricing.validateConfiguration(), []);
});

test("Essential Monthly uses the approved unlimited conversation offer", () => {
  const plan = pricing.getPlan(pricing.plan_ids.ESSENTIAL_MONTHLY);
  assert.equal(plan.billing_amount, 11.99);
  assert.equal(plan.all_access, false);
  assert.equal(plan.in_app_purchases_enabled, true);
  assert.equal(plan.advanced_readings_included, false);
  assert.equal(plan.monthly_question_limit, "unlimited");
  assert.equal(plan.question_reset_type, null);
  assert.equal(plan.benefits.unlimited_conversations, true);
  assert.equal(plan.benefit_reset_type, "once_per_subscription_term");
  assert.equal(pricing.canPurchaseAddOns(plan.plan_id), true);
});

test("Essential Annual uses the approved unlimited annual offer", () => {
  const plan = pricing.getPlan(pricing.plan_ids.ESSENTIAL_ANNUAL);
  assert.equal(plan.billing_period, "annual");
  assert.equal(plan.billing_interval_months, 12);
  assert.equal(plan.billing_amount, 108);
  assert.equal(plan.all_access, false);
  assert.equal(plan.in_app_purchases_enabled, true);
  assert.equal(plan.advanced_readings_included, false);
  assert.equal(plan.monthly_question_limit, "unlimited");
  assert.equal(plan.question_reset_type, null);
  assert.equal(plan.benefits.unlimited_conversations, true);
  assert.equal(plan.benefits.relationship_synastry_guidance_included, true);
  assert.equal(plan.benefit_reset_type, "once_per_subscription_term");
  assert.equal(pricing.canPurchaseAddOns(plan.plan_id), true);
});

test("All Access Monthly and Annual accounts unlock every advanced category", () => {
  [pricing.plan_ids.ALL_ACCESS_MONTHLY, pricing.plan_ids.ALL_ACCESS_ANNUAL].forEach((planId) => {
    const plan = pricing.getPlan(planId);
    assert.equal(plan.all_access, true);
    assert.equal(plan.in_app_purchases_enabled, false);
    assert.equal(plan.advanced_readings_included, true);
    assert.equal(plan.monthly_question_limit, "unlimited");
    assert.equal(plan.benefits.unlimited_conversations, true);
    assert.equal(pricing.canPurchaseAddOns(planId), false);
    assert.equal(pricing.shouldShowAddOnPrompts(planId), false);
    assert.equal(pricing.getEffectiveAdvancedEntitlements(planId).length, pricing.add_ons.length);
  });
});

test("All Access Annual includes the approved one-year Inner Circle membership", () => {
  const plan = pricing.getPlan(pricing.plan_ids.ALL_ACCESS_ANNUAL);
  assert.equal(plan.billing_period, "annual");
  assert.equal(plan.billing_interval_months, 12);
  assert.equal(plan.billing_amount, 212);
  assert.equal(plan.inner_circle_membership_months, 12);
  assert.equal(plan.benefits.arabic_parts_lots_included, true);
  assert.equal(plan.benefits.inner_circle_membership_included, true);
});

test("an Essential purchased add-on unlocks only that entitlement", () => {
  const purchased = "ADD_ON_HORARY_READING";
  const entitlements = pricing.getEffectiveAdvancedEntitlements(
    pricing.plan_ids.ESSENTIAL_MONTHLY,
    [purchased]
  );

  assert.deepEqual(entitlements, [purchased]);
  assert.equal(pricing.shouldShowAddOnPrompts(pricing.plan_ids.ESSENTIAL_MONTHLY), false);
  pricing.add_ons.forEach((addOn) => {
    assert.equal(addOn.is_active, false);
    assert.equal(addOn.price_usd, null);
    assert.equal(addOn.paypal_product_id, null);
  });
});

test("only a completed PayPal payment can pass the payment gate", () => {
  assert.equal(pricing.canGrantAccessForPayment("COMPLETED"), true);
  assert.equal(pricing.canGrantAccessForPayment("completed"), true);
  ["FAILED", "CANCELLED", "CANCELED", "PENDING", "INCOMPLETE", ""].forEach((status) => {
    assert.equal(pricing.canGrantAccessForPayment(status), false);
  });
});

test("all four active plan account states evaluate as active", () => {
  Object.values(pricing.plan_ids).forEach((planId) => {
    const state = pricing.evaluateAccountState({
      plan_id: planId,
      payment_status: "COMPLETED",
      access_end: futureAccessEnd
    }, evaluationDate);

    assert.equal(state.active, true);
    assert.equal(state.expired, false);
    assert.equal(state.reason, "active");
  });
});

test("expired Essential and All Access accounts remain expired", () => {
  [pricing.plan_ids.ESSENTIAL_MONTHLY, pricing.plan_ids.ALL_ACCESS_ANNUAL].forEach((planId) => {
    const state = pricing.evaluateAccountState({
      plan_id: planId,
      payment_status: "COMPLETED",
      access_end: pastAccessEnd
    }, evaluationDate);

    assert.equal(state.active, false);
    assert.equal(state.expired, true);
    assert.equal(state.reason, "access_expired");
  });
});

test("existing active legacy access is preserved without repurchase", () => {
  const state = pricing.evaluateAccountState({
    plan_id: "LEGACY_FIXED_ACCESS",
    payment_status: "",
    legacy_active: true,
    access_end: futureAccessEnd
  }, evaluationDate);

  assert.equal(state.active, true);
  assert.equal(state.reason, "legacy_active_preserved");
  assert.equal(pricing.existing_user_protection.preserve_existing_active_access, true);
  assert.equal(pricing.existing_user_protection.force_repurchase, false);
  assert.equal(pricing.existing_user_protection.migration_enabled, false);
});

test("USD remains the only checkout currency and local estimates are display-only", () => {
  Object.values(pricing.plans).forEach((plan) => {
    assert.equal(plan.billing_currency, "USD");
    assert.equal(plan.payment_provider, "paypal");
    assert.equal(plan.checkout_enabled, false);
  });

  assert.equal(pricing.payment.primary_checkout_currency, "USD");
  assert.equal(pricing.payment.payment_provider, "paypal");
  assert.equal(pricing.local_currency_display.display_only, true);
  assert.equal(pricing.local_currency_display.controls_access, false);
  assert.equal(pricing.local_currency_display.replaces_usd_checkout, false);
});

test("all required entitlement and payment audit fields are declared", () => {
  [
    "user_id",
    "email",
    "plan_id",
    "access_start",
    "access_end",
    "monthly_question_limit",
    "monthly_questions_used",
    "payment_provider",
    "payment_transaction_id",
    "paypal_transaction_id",
    "original_checkout_currency",
    "original_checkout_amount",
    "payment_status",
    "auto_renew",
    "created_at",
    "updated_at"
  ].forEach((field) => {
    assert.ok(pricing.required_entitlement_fields.includes(field), `missing ${field}`);
  });
});

test("PayPal placeholders remain empty and no frontend secrets are permitted", () => {
  Object.values(pricing.paypal_product_placeholders).forEach((productId) => {
    assert.equal(productId, null);
  });
  assert.equal(pricing.payment.product_ids_configured, false);
  assert.equal(pricing.payment.secrets_allowed_in_frontend, false);
});
