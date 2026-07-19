(function initAstromegPricingConfig(root, factory) {
  const config = factory();

  if (typeof module === "object" && module.exports) {
    module.exports = config;
  }

  if (root) {
    root.ASTROMEG_PRICING_CONFIG = config;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function createPricingConfig() {
  "use strict";

  const CONFIGURATION_STATUS = "draft_app_preview_only";
  const UNLIMITED = "unlimited";
  const BENEFIT_RESET_TYPES = Object.freeze([
    "first_activation_only",
    "once_per_subscription_term",
    "once_per_billing_month",
    "manual_admin_grant"
  ]);

  const PLAN_IDS = Object.freeze({
    ESSENTIAL_MONTHLY: "ORACLE_ESSENTIAL_MONTHLY",
    ESSENTIAL_ANNUAL: "ORACLE_ESSENTIAL_ANNUAL",
    ALL_ACCESS_MONTHLY: "ORACLE_ALL_ACCESS_MONTHLY",
    ALL_ACCESS_ANNUAL: "ORACLE_ALL_ACCESS_ANNUAL"
  });

  const PAYPAL_PRODUCT_PLACEHOLDERS = Object.freeze({
    ORACLE_ESSENTIAL_MONTHLY_USD_PAYPAL: null,
    ORACLE_ESSENTIAL_ANNUAL_USD_PAYPAL: null,
    ORACLE_ALL_ACCESS_MONTHLY_USD_PAYPAL: null,
    ORACLE_ALL_ACCESS_ANNUAL_USD_PAYPAL: null
  });

  const essentialBenefits = Object.freeze({
    natal_chart_reading_included: true,
    planetary_attunement_included: true,
    daily_guidance_included: true,
    weekly_forecast_included: true,
    draconic_chart_reading_included: true,
    advanced_readings_locked: true,
    upgrade_to_all_access_allowed: true,
    unlimited_conversations: false,
    transit_predictive_guidance_included: false,
    relationship_synastry_guidance_included: false,
    learning_study_features_included: false,
    show_locked_advanced_reading_overlays: true,
    show_add_on_purchase_prompts_when_catalog_active: true
  });

  const essentialMonthlyBenefits = Object.freeze({
    ...essentialBenefits,
    unlimited_conversations: true,
    transit_predictive_guidance_included: true,
    learning_study_features_included: true
  });

  const essentialAnnualBenefits = Object.freeze({
    ...essentialMonthlyBenefits,
    relationship_synastry_guidance_included: true
  });

  const allAccessBenefits = Object.freeze({
    natal_chart_reading_included: true,
    planetary_attunement_included: true,
    daily_guidance_included: true,
    weekly_forecast_included: true,
    draconic_chart_reading_included: true,
    advanced_readings_locked: false,
    upgrade_to_all_access_allowed: false,
    unlimited_conversations: true,
    transit_predictive_guidance_included: true,
    relationship_synastry_guidance_included: true,
    learning_study_features_included: true,
    show_locked_advanced_reading_overlays: false,
    show_add_on_purchase_prompts_when_catalog_active: false
  });

  const allAccessAnnualBenefits = Object.freeze({
    ...allAccessBenefits,
    arabic_parts_lots_included: true,
    inner_circle_membership_included: true
  });

  const plans = {
    [PLAN_IDS.ESSENTIAL_MONTHLY]: {
      plan_id: PLAN_IDS.ESSENTIAL_MONTHLY,
      plan_name: "Oracle Essential",
      billing_period: "monthly",
      billing_interval_months: 1,
      billing_currency: "USD",
      billing_amount: 11.99,
      payment_provider: "paypal",
      access_type: "core_access",
      in_app_purchases_enabled: true,
      all_access: false,
      advanced_readings_included: false,
      monthly_question_limit: UNLIMITED,
      question_reset_type: null,
      natal_reading_quantity: UNLIMITED,
      planetary_attunement_quantity: UNLIMITED,
      draconic_reading_quantity: 0,
      benefit_reset_type: "once_per_subscription_term",
      benefits: essentialMonthlyBenefits,
      paypal_product_placeholder: "ORACLE_ESSENTIAL_MONTHLY_USD_PAYPAL",
      paypal_product_id: null,
      checkout_enabled: false,
      auto_renew_default: null,
      configuration_status: CONFIGURATION_STATUS
    },
    [PLAN_IDS.ESSENTIAL_ANNUAL]: {
      plan_id: PLAN_IDS.ESSENTIAL_ANNUAL,
      plan_name: "Oracle Essential",
      billing_period: "annual",
      billing_interval_months: 12,
      billing_currency: "USD",
      billing_amount: 108,
      payment_provider: "paypal",
      access_type: "core_access",
      in_app_purchases_enabled: true,
      all_access: false,
      advanced_readings_included: false,
      monthly_question_limit: UNLIMITED,
      question_reset_type: null,
      natal_reading_quantity: UNLIMITED,
      planetary_attunement_quantity: UNLIMITED,
      draconic_reading_quantity: 0,
      benefit_reset_type: "once_per_subscription_term",
      benefits: essentialAnnualBenefits,
      paypal_product_placeholder: "ORACLE_ESSENTIAL_ANNUAL_USD_PAYPAL",
      paypal_product_id: null,
      checkout_enabled: false,
      auto_renew_default: null,
      configuration_status: CONFIGURATION_STATUS
    },
    [PLAN_IDS.ALL_ACCESS_MONTHLY]: {
      plan_id: PLAN_IDS.ALL_ACCESS_MONTHLY,
      plan_name: "Oracle All Access",
      billing_period: "monthly",
      billing_interval_months: 1,
      billing_currency: "USD",
      billing_amount: 19,
      payment_provider: "paypal",
      access_type: "full_access",
      in_app_purchases_enabled: false,
      all_access: true,
      advanced_readings_included: true,
      monthly_question_limit: UNLIMITED,
      question_reset_type: null,
      natal_reading_quantity: UNLIMITED,
      planetary_attunement_quantity: UNLIMITED,
      draconic_reading_quantity: UNLIMITED,
      benefit_reset_type: "once_per_subscription_term",
      benefits: allAccessBenefits,
      paypal_product_placeholder: "ORACLE_ALL_ACCESS_MONTHLY_USD_PAYPAL",
      paypal_product_id: null,
      checkout_enabled: false,
      auto_renew_default: null,
      configuration_status: CONFIGURATION_STATUS
    },
    [PLAN_IDS.ALL_ACCESS_ANNUAL]: {
      plan_id: PLAN_IDS.ALL_ACCESS_ANNUAL,
      plan_name: "Oracle All Access",
      billing_period: "annual",
      billing_interval_months: 12,
      billing_currency: "USD",
      billing_amount: 212,
      payment_provider: "paypal",
      access_type: "full_access",
      in_app_purchases_enabled: false,
      all_access: true,
      advanced_readings_included: true,
      monthly_question_limit: UNLIMITED,
      question_reset_type: null,
      natal_reading_quantity: UNLIMITED,
      planetary_attunement_quantity: UNLIMITED,
      draconic_reading_quantity: UNLIMITED,
      inner_circle_membership_months: 12,
      benefit_reset_type: "once_per_subscription_term",
      benefits: allAccessAnnualBenefits,
      paypal_product_placeholder: "ORACLE_ALL_ACCESS_ANNUAL_USD_PAYPAL",
      paypal_product_id: null,
      checkout_enabled: false,
      auto_renew_default: null,
      configuration_status: CONFIGURATION_STATUS
    }
  };

  const addOnNames = [
    ["ADD_ON_ADVANCED_TRANSIT_READING", "Advanced Transit Reading", "advanced_transit"],
    ["ADD_ON_SOLAR_RETURN_READING", "Solar Return Reading", "solar_return"],
    ["ADD_ON_SYNASTRY_RELATIONSHIP_READING", "Synastry / Relationship Reading", "synastry_relationship"],
    ["ADD_ON_CAREER_BUSINESS_READING", "Career / Business Reading", "career_business"],
    ["ADD_ON_MONEY_WEALTH_TIMING", "Money / Wealth Timing", "money_wealth_timing"],
    ["ADD_ON_HORARY_READING", "Horary Reading", "horary"],
    ["ADD_ON_DRACONIC_DEEP_DIVE", "Draconic Deep Dive", "draconic_deep_dive"],
    ["ADD_ON_KARMA_HEALING_READING", "Karma / Healing Reading", "karma_healing"],
    ["ADD_ON_RELOCATION_READING", "Relocation Reading", "relocation"],
    ["ADD_ON_PREDICTIVE_TIMING_REPORT", "Predictive Timing Report", "predictive_timing"]
  ];

  const addOns = addOnNames.map(([addOnId, addOnName, category]) => ({
    add_on_id: addOnId,
    add_on_name: addOnName,
    category,
    price_usd: null,
    estimated_local_currency: null,
    estimated_local_amount: null,
    entitlement_type: "single_reading",
    usage_quantity: 1,
    access_duration: null,
    paypal_product_id: null,
    is_active: false,
    configuration_status: CONFIGURATION_STATUS
  }));

  const entitlementFieldSchema = {
    user_id: "string",
    email: "string",
    plan_id: "string",
    plan_name: "string",
    billing_currency: "string",
    billing_amount: "number",
    billing_period: "string",
    displayed_estimated_currency: "string|null",
    displayed_estimated_amount: "number|null",
    exchange_rate_source: "string|null",
    exchange_rate_timestamp: "datetime|null",
    buyer_country: "string|null",
    original_checkout_currency: "string",
    original_checkout_amount: "number",
    payment_status: "string",
    paypal_transaction_id: "string|null",
    access_start: "datetime",
    access_end: "datetime",
    subscription_status: "string",
    all_access: "boolean",
    monthly_question_limit: "number|unlimited",
    monthly_questions_used: "number",
    advanced_readings_included: "boolean",
    in_app_purchases_enabled: "boolean",
    natal_reading_quantity: "number|unlimited",
    planetary_attunement_quantity: "number|unlimited",
    draconic_reading_quantity: "number|unlimited",
    benefit_reset_type: "string",
    payment_provider: "string",
    payment_transaction_id: "string|null",
    auto_renew: "boolean|null",
    created_at: "datetime",
    updated_at: "datetime"
  };

  const paymentConfiguration = {
    primary_checkout_currency: "USD",
    checkout_currency_locked: true,
    payment_provider: "paypal",
    accepted_payment_methods: ["credit_card_via_paypal", "debit_card_via_paypal"],
    access_grant_payment_statuses: ["COMPLETED"],
    access_denied_payment_statuses: ["FAILED", "CANCELLED", "CANCELED", "PENDING", "INCOMPLETE"],
    checkout_enabled: false,
    product_ids_configured: false,
    secrets_allowed_in_frontend: false,
    auto_renew_behavior: "requires_approval"
  };

  const localCurrencyDisplay = {
    supported: true,
    enabled: false,
    display_only: true,
    controls_access: false,
    replaces_usd_checkout: false,
    exchange_rate_source: null,
    required_display_fields: [
      "displayed_estimated_currency",
      "displayed_estimated_amount",
      "exchange_rate_source",
      "exchange_rate_timestamp",
      "buyer_country"
    ]
  };

  const existingUserProtection = {
    migration_enabled: false,
    preserve_existing_active_access: true,
    force_repurchase: false,
    preserve_legacy_entitlement_behavior: true,
    export_required_before_future_migration: true
  };

  function normalizePaymentStatus(status) {
    return String(status || "").trim().toUpperCase();
  }

  function getPlan(planId) {
    return plans[planId] || null;
  }

  function getAddOn(addOnId) {
    return addOns.find((addOn) => addOn.add_on_id === addOnId) || null;
  }

  function canGrantAccessForPayment(paymentStatus) {
    return paymentConfiguration.access_grant_payment_statuses.includes(
      normalizePaymentStatus(paymentStatus)
    );
  }

  function canPurchaseAddOns(planId) {
    return getPlan(planId)?.in_app_purchases_enabled === true;
  }

  function shouldShowAddOnPrompts(planId) {
    const plan = getPlan(planId);
    return Boolean(
      plan?.benefits.show_add_on_purchase_prompts_when_catalog_active &&
      addOns.some((addOn) => addOn.is_active)
    );
  }

  function getEffectiveAdvancedEntitlements(planId, purchasedAddOnIds = []) {
    const plan = getPlan(planId);
    if (!plan) return [];

    if (plan.all_access) {
      return addOns.map((addOn) => addOn.add_on_id);
    }

    return Array.from(new Set(purchasedAddOnIds))
      .filter((addOnId) => getAddOn(addOnId) !== null);
  }

  function evaluateAccountState(account, nowInput = new Date()) {
    const now = nowInput instanceof Date ? nowInput : new Date(nowInput);
    const accessEnd = account.access_end ? new Date(account.access_end) : null;
    const hasValidAccessEnd = accessEnd && !Number.isNaN(accessEnd.valueOf());

    if (account.legacy_active === true) {
      return {
        active: true,
        expired: false,
        reason: "legacy_active_preserved",
        plan: getPlan(account.plan_id)
      };
    }

    const plan = getPlan(account.plan_id);
    if (!plan) {
      return { active: false, expired: false, reason: "unknown_plan", plan: null };
    }

    if (!canGrantAccessForPayment(account.payment_status)) {
      return { active: false, expired: false, reason: "payment_not_completed", plan };
    }

    if (hasValidAccessEnd && accessEnd <= now) {
      return { active: false, expired: true, reason: "access_expired", plan };
    }

    if (!hasValidAccessEnd) {
      return { active: false, expired: false, reason: "access_window_missing", plan };
    }

    return { active: true, expired: false, reason: "active", plan };
  }

  function validateConfiguration() {
    const errors = [];
    const expectedPlanIds = Object.values(PLAN_IDS);

    if (Object.keys(plans).length !== expectedPlanIds.length) {
      errors.push("Exactly four public plans must be configured.");
    }

    expectedPlanIds.forEach((planId) => {
      const plan = plans[planId];
      if (!plan) {
        errors.push(`Missing plan: ${planId}`);
        return;
      }
      if (plan.billing_currency !== "USD") errors.push(`${planId} must bill in USD.`);
      if (plan.payment_provider !== "paypal") errors.push(`${planId} must use PayPal.`);
      if (plan.checkout_enabled !== false) errors.push(`${planId} checkout must remain disabled in preview.`);
      if (plan.paypal_product_id !== null) errors.push(`${planId} must not contain a live PayPal product ID.`);
      if (!BENEFIT_RESET_TYPES.includes(plan.benefit_reset_type)) {
        errors.push(`${planId} has an unsupported benefit reset type.`);
      }
    });

    addOns.forEach((addOn) => {
      if (addOn.price_usd !== null) errors.push(`${addOn.add_on_id} price must remain unset.`);
      if (addOn.paypal_product_id !== null) errors.push(`${addOn.add_on_id} PayPal ID must remain unset.`);
      if (addOn.is_active !== false) errors.push(`${addOn.add_on_id} must remain inactive.`);
    });

    Object.entries(PAYPAL_PRODUCT_PLACEHOLDERS).forEach(([placeholder, value]) => {
      if (value !== null) errors.push(`${placeholder} must remain an empty placeholder.`);
    });

    if (paymentConfiguration.checkout_enabled !== false) {
      errors.push("Checkout must remain disabled in the app preview.");
    }
    if (paymentConfiguration.secrets_allowed_in_frontend !== false) {
      errors.push("PayPal secrets must never be allowed in frontend code.");
    }

    return errors;
  }

  const publicConfig = {
    version: "2026-07-14",
    configuration_status: CONFIGURATION_STATUS,
    deployment_target: "none",
    checkout_activation_requires_approval: true,
    unlimited_value: UNLIMITED,
    plan_ids: PLAN_IDS,
    plans,
    benefit_reset_types: BENEFIT_RESET_TYPES,
    add_ons: addOns,
    paypal_product_placeholders: PAYPAL_PRODUCT_PLACEHOLDERS,
    payment: paymentConfiguration,
    local_currency_display: localCurrencyDisplay,
    entitlement_field_schema: entitlementFieldSchema,
    required_entitlement_fields: Object.keys(entitlementFieldSchema),
    existing_user_protection: existingUserProtection,
    getPlan,
    getAddOn,
    canGrantAccessForPayment,
    canPurchaseAddOns,
    shouldShowAddOnPrompts,
    getEffectiveAdvancedEntitlements,
    evaluateAccountState,
    validateConfiguration
  };

  function deepFreeze(value, seen = new WeakSet()) {
    if (!value || typeof value !== "object" || Object.isFrozen(value) || seen.has(value)) {
      return value;
    }

    seen.add(value);
    Object.getOwnPropertyNames(value).forEach((key) => deepFreeze(value[key], seen));
    return Object.freeze(value);
  }

  return deepFreeze(publicConfig);
});
