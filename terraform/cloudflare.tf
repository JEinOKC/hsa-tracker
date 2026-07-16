# Cloudflare DNS + Pages automation — all resources are gated on cloudflare_enabled.
# Set cloudflare_enabled = false (the default) to skip this entirely and manage
# DNS manually. See docs/deployment.md for manual DNS instructions.

# ── ACM certificate DNS validation ────────────────────────────────────────────
# Adds the CNAME records that ACM needs to validate the API custom domain cert.

resource "cloudflare_record" "acm_validation" {
  for_each = var.cloudflare_enabled && var.api_custom_domain != "" ? {
    for dvo in aws_acm_certificate.api[0].domain_validation_options : dvo.domain_name => dvo
  } : {}

  zone_id = var.cloudflare_zone_id
  name    = each.value.resource_record_name
  type    = each.value.resource_record_type
  content = trimsuffix(each.value.resource_record_value, ".")
  ttl     = 60
  proxied = false # Must be DNS-only for ACM validation
}

# ── API subdomain ──────────────────────────────────────────────────────────────
# Points hsa-api.jameseng.land → API Gateway regional domain.
# Must be DNS-only (proxied = false) — API Gateway handles TLS itself.

resource "cloudflare_record" "api" {
  count = var.cloudflare_enabled && var.api_custom_domain != "" ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = var.api_custom_domain
  type    = "CNAME"
  content = aws_apigatewayv2_domain_name.api[0].domain_name_configuration[0].target_domain_name
  ttl     = 1      # Auto TTL when proxied; 1 = Cloudflare-managed
  proxied = false  # API Gateway terminates TLS — do not proxy
}

# ── Cloudflare Pages project ───────────────────────────────────────────────────

resource "cloudflare_pages_project" "frontend" {
  count             = var.cloudflare_enabled ? 1 : 0
  account_id        = var.cloudflare_account_id
  name              = "hsa-tracker"
  production_branch = "main"

  source {
    type = "github"
    config {
      owner                         = split("/", var.github_repo)[0]
      repo_name                     = split("/", var.github_repo)[1]
      production_branch             = "main"
      pr_comments_enabled           = false
      deployments_enabled           = false
      production_deployment_enabled = false
    }
  }

  build_config {
    build_command   = "npm run build"
    destination_dir = "dist"
    root_dir        = "frontend"
  }

  deployment_configs {
    production {
      environment_variables = {
        VITE_API_URL          = var.api_custom_domain != "" ? "https://${var.api_custom_domain}/api/v1" : "${aws_apigatewayv2_stage.default.invoke_url}api/v1"
        VITE_VAPID_PUBLIC_KEY = var.vapid_public_key
        VITE_WEBAUTHN_RP_ID   = var.webauthn_rp_id
      }
    }
  }
}

# ── Frontend custom domain ─────────────────────────────────────────────────────

resource "cloudflare_pages_domain" "frontend" {
  count      = var.cloudflare_enabled && var.frontend_domain != "" ? 1 : 0
  account_id = var.cloudflare_account_id
  project_name = cloudflare_pages_project.frontend[0].name
  domain     = var.frontend_domain
}

resource "cloudflare_record" "frontend" {
  count = var.cloudflare_enabled && var.frontend_domain != "" ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = var.frontend_domain
  type    = "CNAME"
  content = cloudflare_pages_project.frontend[0].subdomain
  ttl     = 1
  proxied = true # Pages sits behind Cloudflare proxy — this is correct
}
